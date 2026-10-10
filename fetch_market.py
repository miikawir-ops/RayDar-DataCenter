"""
fetch_market.py — Market data pipeline for RayDar Data Center.

Fetches all data needed by score_engine.py from free sources:
  - yfinance  : prices, revenue growth, gross margins, volume, short interest
  - feedparser: news headlines for keyword scoring

Adapted from the parent AI value chain agent's fetch_market.py (reference/).
Sub-layer swap (Part B2 of DATACENTER_RAYDAR_SPEC.md): the parent's single
"Data center" layer becomes 5 sub-layers (cooling/networking/optical/
compute/colocation), defined in config.py. Sub-layer definitions live in
config.py; everything else — including the layer-filtered news scoring
mechanism (v4 fix from the parent, non-negotiable per Part A6) — is reused
unchanged, just remapped from layers to sub-layers.

PLAN.md step 4b: capex-trend fetch for the 4 hyperscalers (MSFT/GOOGL/
AMZN/META), single-quarter YoY snapshot per decision #4. Kept as a
distinct field (capex_yoy_pct) from the existing per-ticker capex_div —
different concept (hyperscaler capex trend overlay vs. a sub-layer
company's own capex/OCF ratio).

Returns:
  run_pipeline()       -> {"sub_layers": {sub_layer_id: [ticker dicts]},
                            "meta": {"generic_feed_failures": [...]}}
  fetch_macro()         -> dict with vix, yield_10y_change, nasdaq_vs_spx_20d
  fetch_capex_trend()   -> list of hyperscaler capex-trend dicts
  fetch_trading_sessions() -> completed US sessions (dates), raises if unavailable
"""

import json
import math
import re
import statistics
import logging
import datetime
import argparse
import feedparser
import pandas as pd
import yfinance as yf
from pathlib import Path
from zoneinfo import ZoneInfo

from config import SUB_LAYERS, CAPEX_TICKERS, MODEL_VERSION, COMPANY_NAMES, GENERIC_BOTTLENECK_KEYWORDS

log = logging.getLogger(__name__)

# ── Session dating (ledger R33b/R36, R40) ─────────────────────────────────────
# Every daily-bar fetch drops a bar dated today (US/Eastern) until the
# session has closed, so a run during US trading hours scores the last
# completed session, not a partial one. Early-close days (13:00 ET) are
# treated as closing at 16:00: a run between 13:00 and 16:00 on those days
# uses the previous session, which is conservative rather than wrong.
US_EASTERN        = ZoneInfo("America/New_York")
SESSION_CLOSE_ET  = datetime.time(16, 0)
SESSION_REFERENCE = "^GSPC"   # trading calendar: one daily bar per US session
MAX_SESSION_AGE_DAYS = 7

# ── Data-format checks (ledger R44) ───────────────────────────────────────────
# A field missing for one company is a data gap (None + data_missing). A field
# missing for EVERY company, or a column missing from the daily bars, means
# yfinance's data format changed; scoring on without it would quietly turn it
# into a 0 or a gap everywhere (as happened to the analyst data, ledger R35),
# so the run fails instead.

class SchemaError(RuntimeError):
    """A column or field the pipeline reads is missing from yfinance's data."""


TICKER_BAR_COLUMNS = ("Close", "Adj Close", "High", "Low", "Volume")

# Buy-side grades counted by the analyst signal (the list the old code used),
# among actions within the last ANALYST_WINDOW_DAYS up to the session
# (ledger R49; the original code had no time window).
BUY_GRADES = ("Buy", "Strong Buy", "Overweight", "Outperform", "Positive")
ANALYST_WINDOW_DAYS = 30
INDEX_BAR_COLUMNS  = ("Close",)

# Per-company fields the pipeline reads; each must be present for at least
# one company in a run.
EXPECTED_FIELDS = (
    "info.marketCap",
    "info.currentPrice|regularMarketPrice",
    "info.grossMargins",
    "info.shortPercentOfFloat",
    "quarterly_financials.Total Revenue|Revenue",
    "quarterly_financials.Gross Profit|GrossProfit",
    "quarterly_cashflow.Capital Expenditure|CapitalExpenditure",
    "quarterly_cashflow.Operating Cash Flow|OperatingCashFlow",
    "upgrades_downgrades.ToGrade",
)

# Known breaks that are already tracked: logged as an error on every run
# instead of failing it, until the fix named here ships. Each one expires:
# once MODEL_VERSION reaches `expires_at` (the release with the fix bumps
# it), or once the field is no longer read at all, the exemption itself fails
# the run until it's removed (ledger R48). Nothing else may be added here
# without Ray's approval.
KNOWN_FORMAT_BREAKS = {}   # the analyst break (ledger R35) was fixed by R45 item 1


def require_columns(hist, columns, label):
    """Raise SchemaError if non-empty daily bars lack a column the pipeline reads."""
    if hist is not None and not hist.empty:
        absent = [c for c in columns if c not in hist.columns]
        if absent:
            raise SchemaError(f"{label}: daily bars have no {absent} column — yfinance data format "
                              "changed? Failing the run rather than scoring without it (ledger R44)")


def check_exemptions():
    """Raise SchemaError if a format-break exemption has expired or is stale (ledger R48)."""
    for field, ex in KNOWN_FORMAT_BREAKS.items():
        if MODEL_VERSION >= ex["expires_at"]:
            raise SchemaError(f"The exemption for {field} expired at model_version {ex['expires_at']} "
                              f"(now {MODEL_VERSION}): remove it from KNOWN_FORMAT_BREAKS, so the "
                              "check covers that field again (ledger R48)")
        if field not in EXPECTED_FIELDS:
            raise SchemaError(f"The exemption for {field} covers a field the pipeline no longer "
                              "reads: remove it from KNOWN_FORMAT_BREAKS (ledger R48)")


def check_fields(tickers: list):
    """Raise SchemaError if an expected field is missing for every company fetched."""
    check_exemptions()
    if not tickers:
        return          # nothing fetched at all: a fetch failure, handled as missing data
    for field in EXPECTED_FIELDS:
        if any(field in t.get("_fields_seen", ()) for t in tickers):
            continue
        if field in KNOWN_FORMAT_BREAKS:
            log.error(f"Known data-format break: {field} is missing for all {len(tickers)} "
                      f"companies — {KNOWN_FORMAT_BREAKS[field]['reason']} (exemption expires at "
                      f"model_version {KNOWN_FORMAT_BREAKS[field]['expires_at']})")
            continue
        raise SchemaError(f"{field} is missing for all {len(tickers)} companies — yfinance data "
                          "format changed? Failing the run rather than scoring without it (ledger R44)")


def drop_unfinished_bar(hist, now: datetime.datetime = None, label: str = ""):
    """
    Return the daily bars without trailing bars that aren't a completed
    session: today's bar while today's US session hasn't closed, and any
    trailing row whose Close is NaN, whatever its date (ledger R41: the
    parent's page showed "ret30": NaN for every ticker on most runs after
    00:00 UTC, consistent with an empty last bar). `now` is for tests;
    default is the current time. Each dropped bar is logged with `label`,
    so a run during US trading hours shows whether yfinance returned an
    unfinished bar (ledger R33b).
    """
    if hist is None or hist.empty:
        return hist
    now_et = (now or datetime.datetime.now(datetime.timezone.utc)).astimezone(US_EASTERN)
    while not hist.empty:
        unfinished = hist.index[-1].date() == now_et.date() and now_et.time() < SESSION_CLOSE_ET
        if unfinished or pd.isna(hist["Close"].iloc[-1]):
            log.info(f"  {label or 'bars'}: dropped {'unfinished' if unfinished else 'empty (NaN close)'} "
                     f"bar dated {hist.index[-1].date()}")
            hist = hist.iloc[:-1]
        else:
            break
    return hist


def _finite_or_none(result: dict, data_missing: list) -> dict:
    """
    Any NaN or infinite number that still reaches a computed value becomes
    None and is named in data_missing (decision #6, ledger R41), so it can't
    be scored or written to the page. price_history loses its NaN points
    and is named if it had any.
    """
    for key, value in result.items():
        if isinstance(value, float) and not math.isfinite(value):
            result[key] = None
            if key not in data_missing:
                data_missing.append(key)
    hist = result.get("price_history")
    if hist and any(not math.isfinite(p) for p in hist):
        keep = [i for i, p in enumerate(hist) if math.isfinite(p)]
        result["price_history"] = [hist[i] for i in keep]
        if result.get("price_history_dates"):           # keep each point's date aligned
            result["price_history_dates"] = [result["price_history_dates"][i] for i in keep]
        if "price_history" not in data_missing:
            data_missing.append("price_history")
    return result


def fetch_trading_sessions(now: datetime.datetime = None) -> list:
    """
    Completed US trading sessions (datetime.date, oldest first) from the
    reference series' daily bars. Colour confirmation takes its expected
    sessions from here, so a market holiday is never reported as a missing
    day (ledger R40).

    Raises instead of returning an empty or stale calendar: without it the
    run would silently treat no sessions as expected, so the run fails
    loudly instead (R40).
    """
    try:
        bars = yf.Ticker(SESSION_REFERENCE).history(period="1mo")
        require_columns(bars, INDEX_BAR_COLUMNS, SESSION_REFERENCE)
        hist = drop_unfinished_bar(bars, now, SESSION_REFERENCE)
    except Exception as e:
        raise RuntimeError(f"Trading-session calendar unavailable ({SESSION_REFERENCE} daily bars): {e}") from e
    if hist is None or hist.empty:
        raise RuntimeError(f"Trading-session calendar unavailable: {SESSION_REFERENCE} returned no completed daily bars")
    sessions = [ts.date() for ts in hist.index]
    today_et = (now or datetime.datetime.now(datetime.timezone.utc)).astimezone(US_EASTERN).date()
    if (today_et - sessions[-1]).days > MAX_SESSION_AGE_DAYS:
        raise RuntimeError(f"Trading-session calendar is stale: latest {SESSION_REFERENCE} session is "
                           f"{sessions[-1]}, more than {MAX_SESSION_AGE_DAYS} days before {today_et}")
    return sessions

GENERIC_FEEDS = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://finance.yahoo.com/news/rssindex",
    "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines",
    "https://www.cnbc.com/id/20910258/device/rss/rss.html",
]

ALL_TICKERS = [
    t for layer in SUB_LAYERS.values()
    for t in layer["tickers"]
]

# Reverse lookup: ticker → sub_layer_id
TICKER_TO_LAYER = {
    ticker: layer_id
    for layer_id, layer in SUB_LAYERS.items()
    for ticker in layer["tickers"]
}


def fetch_ticker_headlines(tickers: list, max_per_ticker: int = 10) -> tuple:
    """
    Fetch Yahoo Finance RSS for each specific ticker.

    v4 fix (from parent, reused unchanged): ticker symbol is stored
    separately and NOT prepended to headline text. Previously:
    f"{ticker} {title}".lower() caused cross-layer contamination —
    one sub-layer's keywords matched another sub-layer's ticker headlines
    because the ticker appeared as text prefix on every headline.

    Now: headlines are cleanly separated by ticker ownership.
    score_news_velocity() filters by layer_tickers to prevent cross-contamination.

    Returns (headlines, failed_tickers). failed_tickers is the set of
    tickers whose feed fetch raised an exception this run — callers use
    this to mark news_velocity as missing rather than a misleadingly
    clean 0.0 (fetch-failure rule, CLAUDE.md).
    """
    headlines = []
    failed_tickers = set()
    for ticker in tickers:
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_ticker]:
                title   = entry.get("title", "")
                summary = entry.get("summary", "")[:200]
                if title:
                    headlines.append({
                        "text":   f"{title} {summary}".lower(),  # NO ticker prefix
                        "title":  " ".join(title.lower().split()),  # story identity across feeds
                        "ticker": ticker.upper(),                  # stored separately
                        "source": "ticker",
                    })
        except Exception as e:
            log.debug(f"  Ticker feed failed ({ticker}): {e}")
            failed_tickers.add(ticker.upper())
    return headlines, failed_tickers


def fetch_generic_headlines(max_per_feed: int = 20) -> tuple:
    """
    Fetch generic business news as supplementary signal.

    Returns (headlines, failed_feeds). failed_feeds is the list of feed
    URLs that raised an exception this run — not attributable to a single
    ticker/sub-layer, so it's surfaced at the pipeline level instead.
    """
    headlines = []
    failed_feeds = []
    for url in GENERIC_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                title   = entry.get("title", "")
                summary = entry.get("summary", "")[:200]
                if title:
                    headlines.append({
                        "text":   f"{title} {summary}".lower(),
                        "title":  " ".join(title.lower().split()),  # story identity across feeds
                        "ticker": "",      # no ticker — generic source
                        "source": "generic",
                    })
        except Exception as e:
            log.warning(f"Generic feed failed ({url}): {e}")
            failed_feeds.append(url)
    return headlines, failed_feeds


def fetch_all_headlines() -> tuple:
    """
    Fetch ticker-specific (primary) + generic (supplementary) headlines.

    Returns (headlines, failed_ticker_feeds, failed_generic_feeds).
    """
    log.info("  Fetching ticker-specific headlines...")
    ticker_headlines, failed_ticker_feeds = fetch_ticker_headlines(ALL_TICKERS, max_per_ticker=10)
    log.info(f"  Got {len(ticker_headlines)} ticker-specific headlines")
    if failed_ticker_feeds:
        log.warning(f"  Ticker feed fetch failed for: {sorted(failed_ticker_feeds)}")

    log.info("  Fetching generic news headlines...")
    generic_headlines, failed_generic_feeds = fetch_generic_headlines(max_per_feed=20)
    log.info(f"  Got {len(generic_headlines)} generic headlines")
    if failed_generic_feeds:
        log.warning(f"  Generic feed fetch failed for: {failed_generic_feeds}")

    return ticker_headlines + generic_headlines, failed_ticker_feeds, failed_generic_feeds


def score_news_velocity(
    headlines: list,
    context_keywords: list,
    brand_keywords: list = None,
    layer_tickers: list = None,
) -> float:
    """
    Score news velocity with sub-layer-ownership filtering.

    v4 fix (from parent, reused unchanged): ticker-specific headlines are
    ONLY counted for the sub-layer that owns that ticker. This prevents
    cross-contamination where one sub-layer's ticker headlines were being
    counted for another sub-layer.

    Brand/context split (added post-4a-checkpoint): a bare brand-name
    mention (e.g. "Vertiv") is guaranteed in almost every headline about
    that ticker regardless of real news content — ownership is already
    established via the headline's `ticker` field. So for TICKER-sourced
    headlines, only a context_keywords hit counts as a real match; brand
    name alone does not. For GENERIC headlines (no ticker field), a brand
    match still counts, since brand name is the only way to tie an
    unattributed headline to a specific company.

    Algorithm (ledger R45 item 3 replaced the brand rule above):
      - Ticker headline (this sub-layer's ticker): 2.0 pts if it has a context
        keyword (this sub-layer's terms or the shared supply terms) AND names
        the company whose feed it came from (config.COMPANY_NAMES, whole word).
      - Generic headline: 1.0 pt only through a term specific to this
        sub-layer. The shared supply keywords ("backlog", "sold out", ...) are
        in every sub-layer's list, so on their own they'd add the same story
        to all five; a bare brand name no longer counts at all.
      - Each story counts once per sub-layer, however many feeds carry it
        (same title); a ticker-feed copy is considered before a generic one.
      - Ticker headline from ANOTHER sub-layer's ticker → SKIPPED entirely.
    brand_keywords is no longer used for scoring.

    Cap: 20 weighted points → scaled to 0-10 output range.
    """
    context_lower  = [kw.lower() for kw in context_keywords]
    shared         = {kw.lower() for kw in GENERIC_BOTTLENECK_KEYWORDS}
    specific_lower = [kw for kw in context_lower if kw not in shared]
    # Normalise layer tickers to uppercase for comparison
    layer_tickers_upper = set(t.upper() for t in (layer_tickers or []))

    def names_company(text: str, ticker: str) -> bool:
        return any(re.search(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", text)
                   for n in COMPANY_NAMES.get(ticker, ()))

    counted = set()
    weighted_hits = 0.0
    ticker_first = sorted(headlines, key=lambda h: 0 if isinstance(h, dict) and h.get("source") == "ticker" else 1)
    for h in ticker_first:
        if isinstance(h, dict):
            text      = h.get("text", "")
            source    = h.get("source", "generic")
            h_ticker  = h.get("ticker", "").upper()
            story     = h.get("title") or text
        else:
            # Legacy string format fallback
            text     = h.lower()
            source   = "generic"
            h_ticker = ""
            story    = text

        # ── Sub-layer ownership filter ──────────────────────────────────────
        # Ticker-specific headlines only count for the sub-layer that owns the ticker
        if source == "ticker" and layer_tickers_upper:
            if h_ticker not in layer_tickers_upper:
                continue   # skip — belongs to a different sub-layer
        if story in counted:
            continue       # the same story from another feed already counted

        if source == "ticker":
            if any(kw in text for kw in context_lower) and names_company(text, h_ticker):
                weighted_hits += 2.0
                counted.add(story)
        elif any(kw in text for kw in specific_lower):
            weighted_hits += 1.0
            counted.add(story)

    # Cap at 20 weighted points, scale to 0-10 output
    return round(min(weighted_hits, 20.0) / 2.0, 1)


def fetch_ticker_data(ticker: str, headlines: list, context_keywords: list,
                      brand_keywords: list = None, layer_tickers: list = None,
                      failed_ticker_feeds: set = None):
    data_missing = []
    try:
        t    = yf.Ticker(ticker)
        info = t.info

        # Prices come from completed-session daily bars only (ledger R42): no
        # live intraday quote reaches scoring or the cards. One unadjusted
        # fetch serves both uses: "Adj Close" is the dividend-adjusted series
        # the signals have always used (identical to the default
        # auto-adjusted Close), while Close/High/Low are the traded prices
        # for the price, the day's move and the 52-week range.
        bars    = t.history(period="1y", auto_adjust=False)
        require_columns(bars, TICKER_BAR_COLUMNS, ticker)
        hist    = drop_unfinished_bar(bars, label=ticker)
        seen    = set()     # expected fields present for this company (check_fields)
        if info.get("marketCap") is not None:
            seen.add("info.marketCap")
        if info.get("currentPrice") or info.get("regularMarketPrice"):
            seen.add("info.currentPrice|regularMarketPrice")
        if info.get("grossMargins") is not None:
            seen.add("info.grossMargins")
        if info.get("shortPercentOfFloat") is not None:
            seen.add("info.shortPercentOfFloat")
        closes  = hist["Adj Close"].tolist() if not hist.empty else []
        traded  = hist["Close"].tolist() if not hist.empty else []

        price = round(float(traded[-1]), 2) if traded else None
        if price is None:
            data_missing.append("price")
        if len(traded) >= 2 and traded[-2]:
            price_act = round((traded[-1] - traded[-2]) / traded[-2], 4)
        else:
            price_act = None
            data_missing.append("price_act")

        year = hist[hist.index > hist.index[-1] - pd.Timedelta(weeks=52)] if not hist.empty else hist
        week52_high = round(float(year["High"].max()), 2) if not year.empty else None
        if week52_high is None:
            data_missing.append("week52_high")
        week52_low = round(float(year["Low"].min()), 2) if not year.empty else None
        if week52_low is None:
            data_missing.append("week52_low")

        # Yahoo's marketCap follows the live quote, so it's rescaled to the
        # session close. (sharesOutstanding x close doesn't work: for DELL it
        # covers one share class only, about half the company.)
        live_quote = info.get("currentPrice") or info.get("regularMarketPrice")
        if info.get("marketCap") and live_quote and traded:
            market_cap = round(info["marketCap"] * traded[-1] / live_quote)
        else:
            market_cap = None
            data_missing.append("market_cap")
        gross_margin = info.get("grossMargins")
        if gross_margin is None:
            data_missing.append("gross_margin")

        # Sparkline: the last six months, sampled back from the last session
        # so the line ends at the session close, with each point's own date
        # for the chart labels (ledger R43).
        recent = hist[hist.index >= hist.index[-1] - pd.DateOffset(months=6)] if not hist.empty else hist
        if not recent.empty:
            step   = max(1, len(recent) // 30)
            picked = recent.iloc[::-step].iloc[:30].iloc[::-1]
            price_history       = [round(float(v), 2) for v in picked["Adj Close"]]
            price_history_dates = [ts.date().isoformat() for ts in picked.index]
        else:
            price_history, price_history_dates = [], []
            data_missing.append("price_history")
        volumes = hist["Volume"].tolist() if not hist.empty else []

        if len(closes) >= 21:
            price_30d = round((closes[-1] / closes[-21] - 1), 4)
        else:
            price_30d = None
            data_missing.append("price_30d_return")

        vol_avg = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else None
        if vol_avg and volumes:
            vol_spike = round(volumes[-1] / vol_avg, 2)
        else:
            vol_spike = None
            data_missing.append("vol_spike")

        # Momentum (ledger R45 item 2): the last 5 sessions' return against the
        # average (compound) 5-session pace of the last 63 sessions (about 90
        # days); 1.0 means exactly in line with that trend. The excess over the pace is measured
        # in units of the pace when the trend is clear, and of the typical
        # 5-session move when the trend is weaker than that noise. For a clear
        # uptrend this is the old ratio. Fixed: two negative returns no longer
        # make a positive momentum, a near-flat 90 days can't blow the ratio up,
        # and the windows are 5 and 63 sessions (the old ones spanned 4
        # sessions, and divided a 62-session return as if it were 18 five-
        # session periods). Fewer than 69 sessions, or a NaN in the window, is
        # missing data.
        window = closes[-69:]
        if len(window) == 69 and all(math.isfinite(c) for c in window):
            ret_5d = closes[-1] / closes[-6] - 1
            pace   = (closes[-1] / closes[-64]) ** (5 / 63) - 1
            moves  = [closes[i] / closes[i - 5] - 1 for i in range(len(closes) - 63, len(closes))]
            scale  = max(abs(pace), statistics.pstdev(moves))
            price_momentum = round(1 + (ret_5d - pace) / scale, 2) if scale > 0 else 1.0
            price_momentum = max(-5.0, min(5.0, price_momentum))
        else:
            price_momentum = None
            data_missing.append("price_momentum")

        growth_curr       = None
        growth_prev       = None
        gm_delta          = None
        revenue_quarterly = None
        financials        = None

        try:
            financials = t.quarterly_financials
            if financials is not None and not financials.empty:
                rev_row = None
                for label in ["Total Revenue", "Revenue"]:
                    if label in financials.index:
                        rev_row = financials.loc[label]
                        break
                if rev_row is not None:
                    seen.add("quarterly_financials.Total Revenue|Revenue")
                    cols = rev_row.dropna()
                    if len(cols) >= 4:
                        q0, q1, q4, q5 = cols.iloc[0], cols.iloc[1], cols.iloc[2], cols.iloc[3]
                        if q4 and q4 != 0:
                            growth_curr = round((q0 - q4) / abs(q4), 4)
                        if q5 and q5 != 0:
                            growth_prev = round((q1 - q5) / abs(q5), 4)

                gm_row   = None
                rev_row2 = None
                for label in ["Gross Profit", "GrossProfit"]:
                    if label in financials.index:
                        gm_row = financials.loc[label]
                        seen.add("quarterly_financials.Gross Profit|GrossProfit")
                        break
                for label in ["Total Revenue", "Revenue"]:
                    if label in financials.index:
                        rev_row2 = financials.loc[label]
                        break
                if gm_row is not None and rev_row2 is not None:
                    gm_cols  = gm_row.dropna()
                    rev_cols = rev_row2.dropna()
                    if len(gm_cols) >= 2 and len(rev_cols) >= 2:
                        gm_c = gm_cols.iloc[0] / rev_cols.iloc[0] if rev_cols.iloc[0] else 0
                        gm_p = gm_cols.iloc[1] / rev_cols.iloc[1] if rev_cols.iloc[1] else 0
                        gm_delta = round(gm_c - gm_p, 4)
        except Exception as e:
            log.debug(f"  {ticker} quarterly error: {e}")

        if gm_delta is None:
            data_missing.append("gm_delta")

        if growth_curr is None:
            try:
                if financials is not None and not financials.empty:
                    for label in ["Total Revenue", "Revenue"]:
                        if label in financials.index:
                            rev_row = financials.loc[label]
                            rev_vals = [v for v in rev_row.values
                                        if v is not None and str(v) != "nan" and v == v]
                            if rev_vals:
                                revenue_quarterly = float(rev_vals[0])
                            break
            except Exception:
                pass
            growth_curr = info.get("revenueGrowth")
        if growth_prev is None:
            growth_prev = info.get("earningsGrowth")

        if revenue_quarterly is None:
            data_missing.append("revenue_quarterly")
        if growth_curr is None:
            data_missing.append("growth_curr")
        if growth_prev is None:
            data_missing.append("growth_prev")

        # Analyst grades (ledger R45 item 1, R49): per-action rows from
        # upgrades_downgrades. t.recommendations is a monthly summary table
        # without grades in yfinance 1.4 and 1.7, which scored every company 0
        # (ledger R35). Counted: how many actions within the 30 days up to the
        # session set a buy-side grade, at most the 10 most recent of them (the
        # original code's limit). No actions in the window is a real 0; a
        # failed fetch or no table at all is missing data (None + data_missing).
        analyst_upgrades = None
        try:
            ud = t.upgrades_downgrades
            if ud is not None and "ToGrade" in ud.columns:
                seen.add("upgrades_downgrades.ToGrade")
                if not ud.empty:
                    session = hist.index[-1].date() if not hist.empty else datetime.date.today()
                    dates   = pd.Index([ts.date() for ts in ud.index])
                    inside  = (dates > session - datetime.timedelta(days=ANALYST_WINDOW_DAYS)) & (dates <= session)
                    recent  = ud[inside].sort_index().tail(10)
                    analyst_upgrades = int(recent["ToGrade"].isin(BUY_GRADES).sum())
        except Exception as e:
            log.debug(f"  {ticker} upgrades_downgrades error: {e}")
        if analyst_upgrades is None:
            data_missing.append("analyst_upgrades")

        short_int_change = None
        try:
            short_info = info.get("shortPercentOfFloat")
            if short_info is not None:
                short_int_change = round((short_info - 0.05) * -1, 4)
            else:
                data_missing.append("short_int_change")
        except Exception:
            data_missing.append("short_int_change")

        capex_div = None
        try:
            cf = t.quarterly_cashflow
            if cf is not None and not cf.empty:
                capex_row = None
                ocf_row   = None
                for label in ["Capital Expenditure", "CapitalExpenditure"]:
                    if label in cf.index:
                        capex_row = cf.loc[label]
                        seen.add("quarterly_cashflow.Capital Expenditure|CapitalExpenditure")
                        break
                for label in ["Operating Cash Flow", "OperatingCashFlow"]:
                    if label in cf.index:
                        ocf_row = cf.loc[label]
                        seen.add("quarterly_cashflow.Operating Cash Flow|OperatingCashFlow")
                        break
                if capex_row is not None and ocf_row is not None:
                    capex_val = abs(capex_row.dropna().iloc[0]) if not capex_row.dropna().empty else None
                    ocf_val   = ocf_row.dropna().iloc[0] if not ocf_row.dropna().empty else None
                    if ocf_val and ocf_val > 0 and capex_val is not None:
                        capex_div = round(min(capex_val / ocf_val, 1.0), 4)
        except Exception as e:
            log.debug(f"  {ticker} capex error: {e}")
        if capex_div is None:
            data_missing.append("capex_div")

        # News velocity — sub-layer-filtered to prevent cross-contamination.
        # Only this sub-layer's ticker headlines + generic headlines are counted.
        # If this ticker's own RSS feed failed, news_velocity is unreliable —
        # a computed 0.0 here would be indistinguishable from a genuine
        # no-signal read, so it's marked missing instead (fetch-failure rule).
        ticker_feed_failed = bool(failed_ticker_feeds) and ticker.upper() in failed_ticker_feeds
        if ticker_feed_failed:
            news_velocity = None
            data_missing.append("news_velocity")
        else:
            news_velocity = score_news_velocity(
                headlines,
                context_keywords,
                brand_keywords=brand_keywords,
                layer_tickers=layer_tickers,   # ← ownership filter
            )

        return _finite_or_none({
            "ticker":            ticker,
            "name":              info.get("longName") or info.get("shortName", ticker),
            "price":             round(float(price), 2) if price is not None else None,
            "currency":          info.get("currency", "USD"),
            "growth_curr":       growth_curr,
            "growth_prev":       growth_prev,
            "gm_delta":          gm_delta,
            "gross_margin":      gross_margin,
            "news_velocity":     news_velocity,
            "capex_div":         capex_div,
            "vol_spike":         vol_spike,
            "price_act":         price_act,
            "analyst_upgrades":  analyst_upgrades,
            "short_int_change":  short_int_change,
            "price_30d_return":  price_30d,
            "price_history":     price_history,
            "price_history_dates": price_history_dates,
            "week52_high":       week52_high,
            "week52_low":        week52_low,
            "market_cap":        market_cap,
            "revenue_quarterly": revenue_quarterly,
            "price_momentum":    price_momentum,
            "peer_outperformance": None,
            "analyst_count":     info.get("numberOfAnalystOpinions", 0),
            "sector":            info.get("sector", "N/A"),
            "data_date":         hist.index[-1].date().isoformat() if not hist.empty else None,
            "data_age_note":     "Quarterly financials may be up to 90 days old",
            "data_missing":      data_missing,
            "_fields_seen":      sorted(seen),
        }, data_missing)

    except SchemaError:
        raise
    except Exception as e:
        log.warning(f"  {ticker}: fetch failed — {e}")
        return None


def add_peer_outperformance(ticker_list: list) -> list:
    valid = [t for t in ticker_list if t and t.get("price_30d_return") is not None]
    if not valid:
        return ticker_list
    avg_30d = sum(t["price_30d_return"] for t in valid) / len(valid)
    for t in ticker_list:
        if t and t.get("price_30d_return") is not None:
            t["peer_outperformance"] = round(t["price_30d_return"] - avg_30d, 4)
    return ticker_list


def fetch_macro() -> dict:
    """
    Each of the three macro signals is fetched independently — one
    signal's failure must not blank out the others (previously a single
    shared try/except meant an exception on the 2nd or 3rd fetch discarded
    an already-successful 1st fetch and returned hardcoded defaults for
    everything). Missing signals are None, listed in data_missing —
    never a hardcoded fallback number (fetch-failure rule, CLAUDE.md).
    """
    log.info("  Fetching macro signals...")
    result = {"vix": None, "yield_10y_change": None, "nasdaq_vs_spx_20d": None}
    data_missing = []

    try:
        # Last completed session's close, not the live quote (ledger R42).
        vix_bars = yf.Ticker("^VIX").history(period="5d")
        require_columns(vix_bars, INDEX_BAR_COLUMNS, "^VIX")
        vix_hist = drop_unfinished_bar(vix_bars, label="^VIX")
        if not vix_hist.empty:
            result["vix"] = round(float(vix_hist["Close"].iloc[-1]), 2)
        else:
            data_missing.append("vix")
    except SchemaError:
        raise
    except Exception as e:
        log.warning(f"  VIX fetch error: {e}")
        data_missing.append("vix")

    try:
        tnx = yf.Ticker("^TNX").history(period="35d")
        require_columns(tnx, INDEX_BAR_COLUMNS, "^TNX")
        tnx = drop_unfinished_bar(tnx, label="^TNX")
        if not tnx.empty and len(tnx) >= 21:
            result["yield_10y_change"] = round(
                (tnx["Close"].iloc[-1] - tnx["Close"].iloc[-21]) * 100, 2
            )
        else:
            data_missing.append("yield_10y_change")
    except SchemaError:
        raise
    except Exception as e:
        log.warning(f"  10Y yield fetch error: {e}")
        data_missing.append("yield_10y_change")

    try:
        nasdaq = yf.Ticker("^IXIC").history(period="25d")
        spx    = yf.Ticker("^GSPC").history(period="25d")
        require_columns(nasdaq, INDEX_BAR_COLUMNS, "^IXIC")
        require_columns(spx, INDEX_BAR_COLUMNS, "^GSPC")
        nasdaq = drop_unfinished_bar(nasdaq, label="^IXIC")
        spx    = drop_unfinished_bar(spx, label="^GSPC")
        if len(nasdaq) >= 20 and len(spx) >= 20:
            nasdaq_ret = nasdaq["Close"].iloc[-1] / nasdaq["Close"].iloc[-20] - 1
            spx_ret    = spx["Close"].iloc[-1]    / spx["Close"].iloc[-20]    - 1
            result["nasdaq_vs_spx_20d"] = round(nasdaq_ret - spx_ret, 4)
        else:
            data_missing.append("nasdaq_vs_spx_20d")
    except SchemaError:
        raise
    except Exception as e:
        log.warning(f"  Nasdaq/SPX fetch error: {e}")
        data_missing.append("nasdaq_vs_spx_20d")

    result = _finite_or_none(result, data_missing)
    result["data_missing"] = data_missing
    if data_missing:
        log.warning(f"  Macro data missing: {data_missing}")
    else:
        log.info(f"  Macro: VIX={result['vix']} "
                 f"yield_chg={result['yield_10y_change']}bps "
                 f"nasdaq_rel={result['nasdaq_vs_spx_20d']*100:.1f}%")
    return result


def _quarter_value(row, idx):
    """NaN-safe positional lookup on a raw (non-dropna'd) cashflow row."""
    if idx >= len(row):
        return None
    v = row.iloc[idx]
    if v is None or v != v:  # NaN check (matches the idiom used elsewhere in this file)
        return None
    return v


def fetch_capex_trend(tickers: list = None) -> list:
    """
    Single-quarter YoY capex snapshot for the hyperscaler capex-trend
    overlay (PLAN.md decision #4). Distinct from the per-ticker capex_div
    field elsewhere in this file — different concept (hyperscaler capex
    trend vs. a sub-layer company's own capex/OCF ratio).

    Method: "latest non-null quarter" is the first non-NaN value scanning
    forward from raw column index 0 (yfinance orders quarterly_cashflow
    columns most-recent-first). "4-back" is +4 on that RAW column index —
    gaps included, not position 4 after dropna(). dropna() would compact
    the column list and silently compare against the wrong fiscal quarter
    with no error — quietly breaking the seasonality control this method
    exists for (see decision #4 in PLAN.md).

    No fallback to the nearest available quarter if the exact 4-back slot
    is NaN or doesn't exist — that ticker is "insufficient data" for this
    run, full stop (fetch-failure rule, CLAUDE.md / decision #6).

    Unlike fetch_ticker_data(), a total fetch failure here still returns
    an entry (data_missing, not a dropped record) rather than None. This
    is intentional, not an inconsistency to "fix": these 4 tickers feed a
    single aggregate capex-direction read (5b), and silently dropping one
    would misrepresent a 3-of-4 aggregate as if it were a 4-of-4 one
    (decision #4's explicit "don't drop an insufficient-data ticker from
    the aggregate silently" rule).
    """
    tickers = tickers or CAPEX_TICKERS
    results = []
    tables_seen, rows_seen = 0, 0       # data-format check (ledger R44)
    for ticker in tickers:
        entry = {
            "ticker":         ticker,
            "capex_yoy_pct":  None,
            "latest_quarter": None,
            "prior_quarter":  None,
            "data_missing":   [],
        }
        try:
            cf = yf.Ticker(ticker).quarterly_cashflow
            if cf is not None and not cf.empty:
                tables_seen += 1
                rows_seen += "Capital Expenditure" in cf.index
            if cf is None or cf.empty or "Capital Expenditure" not in cf.index:
                entry["data_missing"].append("capex_yoy_pct")
                results.append(entry)
                continue

            capex_row = cf.loc["Capital Expenditure"]

            latest_idx = None
            for i in range(len(capex_row)):
                if _quarter_value(capex_row, i) is not None:
                    latest_idx = i
                    break

            if latest_idx is None:
                entry["data_missing"].append("capex_yoy_pct")
                results.append(entry)
                continue

            prior_idx  = latest_idx + 4
            latest_val = _quarter_value(capex_row, latest_idx)
            prior_val  = _quarter_value(capex_row, prior_idx)

            if prior_val is None or prior_val == 0:
                # Exact 4-back slot is NaN or out of range — no fallback
                # to the nearest available quarter (decision #4).
                entry["data_missing"].append("capex_yoy_pct")
            else:
                entry["capex_yoy_pct"]  = round((abs(latest_val) - abs(prior_val)) / abs(prior_val), 4)
                entry["latest_quarter"] = str(capex_row.index[latest_idx].date()) \
                    if hasattr(capex_row.index[latest_idx], "date") else str(capex_row.index[latest_idx])
                entry["prior_quarter"]  = str(capex_row.index[prior_idx].date()) \
                    if hasattr(capex_row.index[prior_idx], "date") else str(capex_row.index[prior_idx])

        except Exception as e:
            log.warning(f"  {ticker}: capex-trend fetch failed — {e}")
            entry["data_missing"].append("capex_yoy_pct")

        results.append(entry)

    if tables_seen and not rows_seen:
        raise SchemaError(f"quarterly_cashflow has no 'Capital Expenditure' row for any of the {tables_seen} "
                          "hyperscalers with data — yfinance data format changed? (ledger R44)")
    reporting = [r for r in results if not r["data_missing"]]
    log.info(f"  Capex trend: {len(reporting)}/{len(tickers)} hyperscalers reporting")
    return results


def run_pipeline(portfolio_file: str = "portfolio.json") -> dict:
    """
    Returns {"sub_layers": {sub_layer_id: [ticker dicts]}, "meta": {...}}.
    "meta" carries pipeline-level flags that aren't attributable to one
    ticker — currently generic_feed_failures (see fetch_generic_headlines).
    """
    log.info("Fetching all headlines (ticker-specific + generic)...")
    headlines, failed_ticker_feeds, failed_generic_feeds = fetch_all_headlines()
    results   = {}
    for layer_id, layer_config in SUB_LAYERS.items():
        log.info(f"  Sub-layer: {layer_config['name']}")
        tickers_data = []
        layer_tickers = layer_config["tickers"]   # pass to filter news correctly
        for ticker in layer_tickers:
            log.info(f"    Fetching {ticker}...")
            data = fetch_ticker_data(
                ticker, headlines,
                layer_config["context_keywords"],
                brand_keywords=layer_config["brand_keywords"],
                layer_tickers=layer_tickers,       # ← ownership filter
                failed_ticker_feeds=failed_ticker_feeds,
            )
            if data:
                tickers_data.append(data)
        tickers_data      = add_peer_outperformance(tickers_data)
        results[layer_id] = tickers_data
        log.info(f"    {len(tickers_data)}/{len(layer_tickers)} tickers OK")
    fetched = [t for ts in results.values() for t in ts]
    check_fields(fetched)
    for t in fetched:
        t.pop("_fields_seen", None)
    return {
        "sub_layers": results,
        "meta": {
            "generic_feed_failures": failed_generic_feeds,
        },
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--macro",  action="store_true", help="Macro data only")
    parser.add_argument("--layer",  type=str, default=None, help="One sub-layer only")
    parser.add_argument("--news",   action="store_true", help="Test news fetch + scoring")
    parser.add_argument("--capex",  action="store_true", help="Hyperscaler capex-trend YoY only")
    args = parser.parse_args()

    if args.capex:
        print("\nFetching hyperscaler capex trend (single-quarter YoY)...")
        capex = fetch_capex_trend()
        for c in capex:
            if c["data_missing"]:
                print(f"  {c['ticker']:<6} insufficient data  (data_missing: {c['data_missing']})")
            else:
                print(f"  {c['ticker']:<6} YoY={c['capex_yoy_pct']*100:>6.1f}%  "
                      f"({c['prior_quarter']} -> {c['latest_quarter']})")
        reporting = [c for c in capex if not c["data_missing"]]
        print(f"\n{len(reporting)}/{len(capex)} hyperscalers reporting")

    elif args.macro:
        print("\nFetching macro signals...")
        macro = fetch_macro()
        print(json.dumps(macro, indent=2))
        if macro.get("data_missing"):
            print(f"\n⚠ Macro data missing this run: {macro['data_missing']}")

    elif args.news:
        print("\nTesting news fetch and velocity scoring (sub-layer-filtered)...")
        headlines, failed_ticker_feeds, failed_generic_feeds = fetch_all_headlines()
        ticker_count  = sum(1 for h in headlines if isinstance(h, dict) and h.get("source") == "ticker")
        generic_count = sum(1 for h in headlines if isinstance(h, dict) and h.get("source") == "generic")
        print(f"\nTotal headlines: {len(headlines)}")
        print(f"  Ticker-specific: {ticker_count} (weight ×2, sub-layer-filtered)")
        print(f"  Generic:         {generic_count} (weight ×1, keyword-matched)")
        if failed_ticker_feeds:
            print(f"\n⚠ Ticker feed fetch failed for: {sorted(failed_ticker_feeds)}")
        if failed_generic_feeds:
            print(f"⚠ Generic feed fetch failed for: {failed_generic_feeds}")

        print("\nNews velocity by sub-layer (filtered — no cross-contamination):")
        for layer_id, layer in SUB_LAYERS.items():
            score = score_news_velocity(
                headlines,
                layer["context_keywords"],
                brand_keywords=layer["brand_keywords"],
                layer_tickers=layer["tickers"],
            )
            bar   = "█" * int(score)
            print(f"  {layer_id:<12} {score:>4.1f}  {bar}")

        print("\nSanity check — cooling sub-layer with NO ownership filter (old broken behaviour):")
        score_unfiltered = score_news_velocity(
            headlines,
            SUB_LAYERS["cooling"]["context_keywords"],
            brand_keywords=SUB_LAYERS["cooling"]["brand_keywords"],
        )
        print(f"  cooling (unfiltered): {score_unfiltered}")
        score_filtered = score_news_velocity(
            headlines,
            SUB_LAYERS["cooling"]["context_keywords"],
            brand_keywords=SUB_LAYERS["cooling"]["brand_keywords"],
            layer_tickers=SUB_LAYERS["cooling"]["tickers"],
        )
        print(f"  cooling (filtered):   {score_filtered}  ← realistic score")

        print("\nHeadline ownership check (cross-contamination check):")
        print("  Each ticker's headlines should only appear under its own sub-layer.")
        for ticker, layer_id in TICKER_TO_LAYER.items():
            n = sum(1 for h in headlines
                     if isinstance(h, dict) and h.get("source") == "ticker"
                     and h.get("ticker", "").upper() == ticker)
            print(f"  {ticker:<6} → {layer_id:<12} ({n} headlines)")

    elif args.layer:
        if args.layer not in SUB_LAYERS:
            print(f"Unknown sub-layer. Choose from: {list(SUB_LAYERS.keys())}")
        else:
            print(f"\nFetching {args.layer} sub-layer only...")
            headlines, failed_ticker_feeds, failed_generic_feeds = fetch_all_headlines()
            if failed_generic_feeds:
                print(f"⚠ Generic feed fetch failed for: {failed_generic_feeds}")
            layer     = SUB_LAYERS[args.layer]
            tickers   = []
            for ticker in layer["tickers"]:
                print(f"  Fetching {ticker}...")
                data = fetch_ticker_data(
                    ticker, headlines,
                    layer["context_keywords"],
                    brand_keywords=layer["brand_keywords"],
                    layer_tickers=layer["tickers"],
                    failed_ticker_feeds=failed_ticker_feeds,
                )
                if data:
                    tickers.append(data)
            tickers = add_peer_outperformance(tickers)
            print(json.dumps(tickers, indent=2, default=str))

    else:
        print("\nRunning full pipeline...")
        pipeline_result  = run_pipeline()
        data             = pipeline_result["sub_layers"]
        generic_failures = pipeline_result["meta"]["generic_feed_failures"]
        if generic_failures:
            print(f"\n⚠ Generic feed fetch failed this run for: {generic_failures}")
        for layer_id, tickers in data.items():
            print(f"\n{layer_id.upper()} — {len(tickers)} tickers")
            for t in tickers:
                g_curr  = t.get("growth_curr")
                g_prev  = t.get("growth_prev")
                delta   = round(g_curr - g_prev, 3) if g_curr and g_prev else "N/A"
                gm      = f"{t.get('gross_margin', 0)*100:.0f}%" if t.get("gross_margin") else "N/A"
                missing = t.get("data_missing") or []
                flag    = f"  ⚠ missing: {missing}" if missing else ""
                print(f"  {t['ticker']:<6} price=${t['price']:<8} "
                      f"growth={str(g_curr):<8} delta={str(delta):<8} "
                      f"GM={gm:<6} news={t.get('news_velocity')}{flag}")
        print(f"\n✅ Pipeline complete — {sum(len(v) for v in data.values())} tickers")

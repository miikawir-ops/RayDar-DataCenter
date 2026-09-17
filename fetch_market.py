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

No capex-trend fetch yet (that's PLAN.md step 4b). This step only swaps
the sub-layer structure and re-validates the news scoring against it.

Returns two objects:
  run_pipeline() -> dict of {sub_layer_id: [list of ticker dicts]}
  fetch_macro()  -> dict with vix, yield_10y_change, nasdaq_vs_spx_20d
"""

import json
import logging
import datetime
import argparse
import feedparser
import yfinance as yf
from pathlib import Path

from config import SUB_LAYERS

log = logging.getLogger(__name__)

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

    Algorithm:
      - Ticker headline (this sub-layer's ticker) + context keyword match → 2.0 pts
      - Ticker headline + brand-name-only (no context keyword)            → 0 pts
      - Generic headline + context OR brand keyword match                  → 1.0 pts
      - Ticker headline from ANOTHER sub-layer's ticker                    → SKIPPED entirely

    Cap: 20 weighted points → scaled to 0-10 output range.
    """
    context_lower = [kw.lower() for kw in context_keywords]
    brand_lower   = [kw.lower() for kw in (brand_keywords or [])]
    # Normalise layer tickers to uppercase for comparison
    layer_tickers_upper = set(t.upper() for t in (layer_tickers or []))

    weighted_hits = 0.0
    for h in headlines:
        if isinstance(h, dict):
            text      = h.get("text", "")
            source    = h.get("source", "generic")
            h_ticker  = h.get("ticker", "").upper()
        else:
            # Legacy string format fallback
            text     = h.lower()
            source   = "generic"
            h_ticker = ""

        # ── Sub-layer ownership filter ──────────────────────────────────────
        # Ticker-specific headlines only count for the sub-layer that owns the ticker
        if source == "ticker" and layer_tickers_upper:
            if h_ticker not in layer_tickers_upper:
                continue   # skip — belongs to a different sub-layer

        has_context = any(kw in text for kw in context_lower)
        has_brand   = any(kw in text for kw in brand_lower)

        if source == "ticker":
            # Ownership already established via h_ticker — brand-name text
            # match alone is tautological and doesn't count. Needs topical content.
            if has_context:
                weighted_hits += 2.0
        else:
            if has_context or has_brand:
                weighted_hits += 1.0

    # Cap at 20 weighted points, scale to 0-10 output
    return round(min(weighted_hits, 20.0) / 2.0, 1)


def fetch_ticker_data(ticker: str, headlines: list, context_keywords: list,
                      brand_keywords: list = None, layer_tickers: list = None,
                      failed_ticker_feeds: set = None):
    data_missing = []
    try:
        t    = yf.Ticker(ticker)
        info = t.info

        price = (info.get("currentPrice")
                 or info.get("regularMarketPrice")
                 or info.get("previousClose"))
        if price is None:
            data_missing.append("price")

        prev_close = info.get("previousClose")
        if prev_close and price is not None:
            price_act = round((price - prev_close) / prev_close, 4)
        else:
            price_act = None
            data_missing.append("price_act")

        week52_high = info.get("fiftyTwoWeekHigh")
        if week52_high is None:
            data_missing.append("week52_high")
        week52_low = info.get("fiftyTwoWeekLow")
        if week52_low is None:
            data_missing.append("week52_low")
        market_cap = info.get("marketCap")
        if market_cap is None:
            data_missing.append("market_cap")
        gross_margin = info.get("grossMargins")
        if gross_margin is None:
            data_missing.append("gross_margin")

        hist    = t.history(period="6mo")
        closes  = hist["Close"].tolist() if not hist.empty else []
        if closes:
            step = max(1, len(closes) // 30)
            price_history = [round(closes[i], 2) for i in range(0, len(closes), step)][-30:]
        else:
            price_history = []
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

        if len(closes) >= 5:
            ret_5d  = closes[-1] / closes[-5] - 1
            ret_90d = (closes[-1] / closes[-63] - 1) if len(closes) >= 63 else ret_5d
            avg_5d_from_90d = ret_90d / 18 if ret_90d != 0 else 0.001
            price_momentum  = round(ret_5d / avg_5d_from_90d, 2) if avg_5d_from_90d != 0 else 1.0
            price_momentum  = max(-5.0, min(5.0, price_momentum))
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

        analyst_upgrades = 0
        try:
            recs = t.recommendations
            if recs is not None and not recs.empty:
                recent = recs.tail(10)
                if "To Grade" in recent.columns:
                    up = recent[recent["To Grade"].isin([
                        "Buy", "Strong Buy", "Overweight", "Outperform", "Positive"
                    ])]
                    analyst_upgrades = len(up)
            # else: call succeeded, genuinely no recent recommendation data —
            # real 0, not a fetch failure.
        except Exception as e:
            log.debug(f"  {ticker} recommendations error: {e}")
            analyst_upgrades = None
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
                        break
                for label in ["Operating Cash Flow", "OperatingCashFlow"]:
                    if label in cf.index:
                        ocf_row = cf.loc[label]
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

        return {
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
            "week52_high":       week52_high,
            "week52_low":        week52_low,
            "market_cap":        market_cap,
            "revenue_quarterly": revenue_quarterly,
            "price_momentum":    price_momentum,
            "peer_outperformance": None,
            "analyst_count":     info.get("numberOfAnalystOpinions", 0),
            "sector":            info.get("sector", "N/A"),
            "data_date":         datetime.datetime.now().strftime("%Y-%m-%d"),
            "data_age_note":     "Quarterly financials may be up to 90 days old",
            "data_missing":      data_missing,
        }

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
        vix_info = yf.Ticker("^VIX").info
        vix_val  = vix_info.get("regularMarketPrice") or vix_info.get("previousClose")
        if vix_val is not None:
            result["vix"] = round(vix_val, 2)
        else:
            data_missing.append("vix")
    except Exception as e:
        log.warning(f"  VIX fetch error: {e}")
        data_missing.append("vix")

    try:
        tnx = yf.Ticker("^TNX").history(period="35d")
        if not tnx.empty and len(tnx) >= 21:
            result["yield_10y_change"] = round(
                (tnx["Close"].iloc[-1] - tnx["Close"].iloc[-21]) * 100, 2
            )
        else:
            data_missing.append("yield_10y_change")
    except Exception as e:
        log.warning(f"  10Y yield fetch error: {e}")
        data_missing.append("yield_10y_change")

    try:
        nasdaq = yf.Ticker("^IXIC").history(period="25d")
        spx    = yf.Ticker("^GSPC").history(period="25d")
        if len(nasdaq) >= 20 and len(spx) >= 20:
            nasdaq_ret = nasdaq["Close"].iloc[-1] / nasdaq["Close"].iloc[-20] - 1
            spx_ret    = spx["Close"].iloc[-1]    / spx["Close"].iloc[-20]    - 1
            result["nasdaq_vs_spx_20d"] = round(nasdaq_ret - spx_ret, 4)
        else:
            data_missing.append("nasdaq_vs_spx_20d")
    except Exception as e:
        log.warning(f"  Nasdaq/SPX fetch error: {e}")
        data_missing.append("nasdaq_vs_spx_20d")

    result["data_missing"] = data_missing
    if data_missing:
        log.warning(f"  Macro data missing: {data_missing}")
    else:
        log.info(f"  Macro: VIX={result['vix']} "
                 f"yield_chg={result['yield_10y_change']}bps "
                 f"nasdaq_rel={result['nasdaq_vs_spx_20d']*100:.1f}%")
    return result


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
    args = parser.parse_args()

    if args.macro:
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

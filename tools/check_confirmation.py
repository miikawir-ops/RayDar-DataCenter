"""Checks for session dating, missing-day handling in colour confirmation,
NaN values, session-dated prices, the data-format check and the R45 input
fixes (PLAN.md ledger R33b, R33d, R39-R45, R48). Offline: yfinance is stubbed, and every
file the pipeline writes (scores_history.json, audit_log.json, index.html)
goes to a temporary folder, never the repo.

What it covers:
  - drop_unfinished_bar(): today's bar is dropped until 16:00 US/Eastern,
    on both sides of the 1 November daylight-saving change, and any trailing
    row whose Close is NaN is dropped whatever its date (R41).
  - NaN values (R41): a NaN that reaches a computed value (30-day return,
    momentum, volume spike, macro) becomes None and is named in
    data_missing; one that still reaches the page data fails the run.
  - fetch_trading_sessions(): the calendar comes from ^GSPC daily bars; a
    failed, empty or stale fetch raises, and stage_fetch() lets it fail the
    run instead of continuing with no sessions expected.
  - The confirmation window: a session with no stored score is left out and
    named in the note, never counted as 0. Cases: a run that never started
    (2026-10-05), a stored entry without this sub-layer's score, a market
    holiday (Thanksgiving, not missing), sessions before the history began
    (not missing), the 7-day limit, and a re-run within the same session.
  - load_scores_history(): an unreadable file is an error in CI only.
  - save_scores_history(): entries are dated by session; a re-run replaces.
  - Audit log (R33c): one entry per ticker per session with its inputs and
    model_version, a re-run replaces, no cap, an unreadable file fails in CI.
  - Workflow (R33a): the build restores both files from the data branch and
    has only read access; a separate save job, the only one with
    contents: write, pushes them back; a failed save opens the failure issue.
  - Prices from bars (R42): price, the day's move and the 52-week range come
    from completed-session bars, the signals from the adjusted close, and
    the market cap is rescaled to the session close; VIX is the last
    session's close.
  - End to end through stage_score() and generate_dashboard(): the card
    note on the rendered page names the missing day (R40), with R42's
    wording, the dated score delta, the data line and the price's date;
    and with no history, the page line and the no-history note.
  - Header and chart (R43): the run time is labelled UTC, and the sparkline
    ends at the session close with each point's own session date.
  - Data format (R44): a missing bar column, or a field missing for every
    company, fails the run (stage_fetch doesn't swallow it); a field missing
    for one company doesn't; the known analyst break is logged, not raised,
    until its exemption expires (model_version 2, R48).
  - Input fixes (R45): analyst grades from upgrades_downgrades (missing data is
    None, never 0); momentum with the right sign, a bounded near-flat case and
    5/63-session windows; news counted once per story, ticker-feed stories
    naming the company, generic headlines only through sub-layer terms; and
    model_version on every history and audit entry.

    python tools/check_confirmation.py
    python tools/check_confirmation.py --shots Output/screenshots/dashboard/r40

--shots also saves the rendered sub-layer cards as a PNG (needs Playwright).
Exit code 0 when every check passes, 1 otherwise.
"""
import argparse
import datetime
import json
import logging
import os
import re
import sys
import tempfile

import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import fetch_market  # noqa: E402
from config import SUB_LAYERS  # noqa: E402
import main          # noqa: E402
import render        # noqa: E402

logging.getLogger().setLevel(logging.WARNING)
UTC = datetime.timezone.utc
D = datetime.date.fromisoformat
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def bars(dates):
    """Daily bars indexed the way yfinance does: midnight US/Eastern."""
    idx = pd.DatetimeIndex([pd.Timestamp(d).tz_localize("America/New_York") for d in dates])
    return pd.DataFrame({"Close": range(len(dates)), "Volume": range(len(dates))}, index=idx)


def price_bars(n, end="2026-10-09", nan_at=(), vol_nan_at=(), trailing_nan=(), adj_factor=1.0, closes=None):
    """n weekday bars ending at `end` with rising closes, shaped like
    history(auto_adjust=False): traded Close/High/Low plus "Adj Close", which
    is Close x adj_factor on every bar but the last (as after a dividend).
    NaN at the given positions, plus trailing rows (by date) that are all NaN."""
    days = [d.date() for d in pd.bdate_range(end=end, periods=n)]
    close = list(closes) if closes is not None else [100.0 + 0.5 * i for i in range(n)]
    vol = [1.0e6] * n
    for i in nan_at:
        close[i] = float("nan")
    for i in vol_nan_at:
        vol[i] = float("nan")
    adj = [c * adj_factor for c in close[:-1]] + close[-1:]
    days += [D(d) for d in trailing_nan]
    nan = [float("nan")] * len(trailing_nan)
    close, vol, adj = close + nan, vol + nan, adj + nan
    idx = pd.DatetimeIndex([pd.Timestamp(d).tz_localize("America/New_York") for d in days])
    return pd.DataFrame({"Close": close, "High": [c + 1 for c in close], "Low": [c - 1 for c in close],
                         "Adj Close": adj, "Volume": vol}, index=idx)


def calendar(start, end, holidays=()):
    """Weekday sessions between start and end, minus the given holidays."""
    out, d = [], D(start)
    while d <= D(end):
        if d.weekday() < 5 and d.isoformat() not in holidays:
            out.append(d)
        d += datetime.timedelta(days=1)
    return out


SESSIONS = calendar("2026-09-14", "2026-12-04", holidays=("2026-11-26",))   # Thanksgiving closed


def entry(date, layers):
    return {"date": date, "time": "18:00",
            "scores": {lid: ({"score": s, "color": c} if s is not None else {"color": c})
                       for lid, (s, c) in layers.items()}}


class StubTicker:
    def __init__(self, hist=None, exc=None):
        self.hist, self.exc = hist, exc

    def history(self, period=None, **kwargs):
        if self.exc:
            raise self.exc
        return self.hist


def with_stub(stub, fn):
    real = fetch_market.yf.Ticker
    fetch_market.yf.Ticker = stub if callable(stub) else (lambda symbol: stub)
    try:
        return fn()
    finally:
        fetch_market.yf.Ticker = real


class FullStub(StubTicker):
    """Enough of yfinance.Ticker for fetch_ticker_data() and fetch_macro()."""
    def __init__(self, hist, info=None):
        super().__init__(hist)
        self.info = info or {"currentPrice": 120.0, "previousClose": 119.0, "fiftyTwoWeekHigh": 130.0,
                             "fiftyTwoWeekLow": 90.0, "marketCap": 1e11, "grossMargins": 0.4,
                             "shortPercentOfFloat": 0.03, "longName": "Test Co"}
        self.quarterly_financials = pd.DataFrame()
        self.quarterly_cashflow = pd.DataFrame()
        self.recommendations = None
        self.upgrades_downgrades = None


def nan_free(d):
    return not any(isinstance(v, float) and v != v for v in d.values()) and \
        not any(p != p for p in d.get("price_history") or [])


def check_nan_values():
    """R41: no NaN reaches a computed value, the history or the page."""
    fetch = lambda hist: with_stub(FullStub(hist), lambda: fetch_market.fetch_ticker_data("TST", [], ["cooling"]))

    # The NaN row is dated a past session, so only the NaN rule (not the
    # unfinished-today rule) can remove it, whenever this check runs.
    good = price_bars(130, end="2026-10-08")
    closes = good["Adj Close"].tolist()
    expected_30d = round(closes[-1] / closes[-21] - 1, 4)
    d = fetch(price_bars(130, end="2026-10-08", trailing_nan=("2026-10-09",)))
    check("ticker: with a trailing NaN row, the 30-day return is computed from the last real close",
          d["price_30d_return"] == expected_30d and "price_30d_return" not in d["data_missing"],
          f'{d["price_30d_return"]} vs {expected_30d}, missing {d["data_missing"]}')
    check("ticker: with a trailing NaN row, the data date is the last real session",
          d["data_date"] == "2026-10-08", d["data_date"])
    check("ticker: with a trailing NaN row, no value is NaN", nan_free(d))

    d = fetch(price_bars(130, nan_at=(-21,)))
    check("ticker: a NaN close 20 sessions back makes the 30-day return None and names it",
          d["price_30d_return"] is None and "price_30d_return" in d["data_missing"] and nan_free(d), str(d["data_missing"]))
    d = fetch(price_bars(130, nan_at=(-5,)))
    check("ticker: a NaN close 4 sessions back makes momentum None, not the +5 maximum",
          d["price_momentum"] is None and "price_momentum" in d["data_missing"] and nan_free(d),
          f'{d["price_momentum"]}, {d["data_missing"]}')
    check("chart: a NaN point is removed together with its date (labels stay aligned)",
          len(d["price_history"]) == len(d["price_history_dates"]) == 29 and "price_history" in d["data_missing"],
          f'{len(d["price_history"])} points, {len(d["price_history_dates"])} dates')
    d = fetch(price_bars(130, vol_nan_at=(-3,)))
    check("ticker: a NaN volume makes the volume spike None and names it",
          d["vol_spike"] is None and "vol_spike" in d["data_missing"] and nan_free(d), str(d["data_missing"]))

    tnx_bad = price_bars(35, nan_at=(-21,))
    stubs = {"^VIX": FullStub(price_bars(5)), "^TNX": FullStub(tnx_bad),
             "^IXIC": FullStub(price_bars(25)), "^GSPC": FullStub(price_bars(25))}
    m = with_stub(lambda symbol: stubs[symbol], fetch_market.fetch_macro)
    check("macro: a NaN in the 10-year yield series makes its change None and names it",
          m["yield_10y_change"] is None and "yield_10y_change" in m["data_missing"]
          and m["nasdaq_vs_spx_20d"] is not None and nan_free(m), str(m))

    try:
        render._capex_js_data({"direction": "stable", "magnitude_pct": float("nan"), "reporting": "4/4",
                               "insufficient": [], "beneficiary_map": {}})
        check("page: a NaN that gets this far fails the run instead of being written", False, "no exception")
    except ValueError:
        check("page: a NaN that gets this far fails the run instead of being written", True)


def check_session_prices():
    """R42: no live quote in scoring or on the cards."""
    info = {"currentPrice": 999.0, "regularMarketPrice": 999.0, "previousClose": 990.0,
            "fiftyTwoWeekHigh": 5000.0, "fiftyTwoWeekLow": 1.0, "marketCap": 2.0e11,
            "grossMargins": 0.4, "shortPercentOfFloat": 0.03, "longName": "Test Co"}
    h = price_bars(260, end="2026-10-09", adj_factor=0.98)
    d = with_stub(FullStub(h, info), lambda: fetch_market.fetch_ticker_data("TST", [], ["cooling"]))
    close, adj = h["Close"].tolist(), h["Adj Close"].tolist()
    check("price: the last completed session's traded close, not the live quote (999)",
          d["price"] == round(close[-1], 2), str(d["price"]))
    check("price: the day's move is the last two session closes",
          d["price_act"] == round((close[-1] - close[-2]) / close[-2], 4), str(d["price_act"]))
    year = h[h.index > h.index[-1] - pd.Timedelta(weeks=52)]
    check("price: the 52-week range comes from the traded highs and lows of the last 52 weeks",
          d["week52_high"] == round(year["High"].max(), 2) and d["week52_low"] == round(year["Low"].min(), 2),
          f'{d["week52_high"]}/{d["week52_low"]}')
    check("price: the market cap is the quote-based one rescaled to the session close",
          d["market_cap"] == round(2.0e11 * close[-1] / 999.0), str(d["market_cap"]))
    check("price: the 30-day return uses the adjusted close, as the signals always have",
          d["price_30d_return"] == round(adj[-1] / adj[-21] - 1, 4), str(d["price_30d_return"]))
    check("price: the data date is the session the price belongs to", d["data_date"] == "2026-10-09")
    dates = d["price_history_dates"]
    check("chart: the sparkline ends at the session close, dated with the session",
          d["price_history"][-1] == round(adj[-1], 2) and dates[-1] == "2026-10-09", f"{d['price_history'][-1:]}, {dates[-1:]}")
    check("chart: 30 points, each with its own session date, oldest first, about six months back",
          len(dates) == len(d["price_history"]) == 30 and dates == sorted(dates)
          and dates[0] >= (D("2026-10-09") - datetime.timedelta(days=186)).isoformat(), f"{len(dates)} {dates[:1]}")
    vix = with_stub(lambda symbol: FullStub(price_bars(25) if symbol != "^VIX" else price_bars(5),
                                            {"regularMarketPrice": 99.0}),
                    fetch_market.fetch_macro)
    check("vix: the last session's close, not the live quote (99)", vix["vix"] == 102.0, str(vix["vix"]))


def check_data_format():
    """R44: a data-format change fails the run instead of scoring as 0 or a gap."""
    def raises(fn):
        try:
            fn()
            return False
        except fetch_market.SchemaError:
            return True

    no_adj = price_bars(130).drop(columns=["Adj Close"])
    check("format: ticker bars without 'Adj Close' fail the run (not a silently dropped company)",
          raises(lambda: with_stub(FullStub(no_adj), lambda: fetch_market.fetch_ticker_data("TST", [], ["cooling"]))))
    stubs = {"^VIX": FullStub(price_bars(5)), "^TNX": FullStub(price_bars(35).drop(columns=["Close"])),
             "^IXIC": FullStub(price_bars(25)), "^GSPC": FullStub(price_bars(25))}
    check("format: index bars without 'Close' fail the run (not a missing macro signal)",
          raises(lambda: with_stub(lambda symbol: stubs[symbol], fetch_market.fetch_macro)))

    d = with_stub(FullStub(price_bars(130)), lambda: fetch_market.fetch_ticker_data("TST", [], ["cooling"]))
    check("format: the fields each company provides are recorded",
          {"info.marketCap", "info.grossMargins", "info.shortPercentOfFloat"} <= set(d["_fields_seen"]), str(d["_fields_seen"]))

    every = list(fetch_market.EXPECTED_FIELDS)
    full = lambda drop=(): {"_fields_seen": [f for f in every if f not in drop]}
    check("format: a field missing for one company only is a data gap, not a failure",
          not raises(lambda: fetch_market.check_fields([full(("info.marketCap",)), full()])))
    check("format: a field missing for every company fails the run",
          raises(lambda: fetch_market.check_fields([full(("info.marketCap",)), full(("info.marketCap",))])))
    # R45 release state: the analyst exemption is gone and its source replaced.
    check("format: the analyst exemption is gone and the check covers upgrades_downgrades",
          fetch_market.KNOWN_FORMAT_BREAKS == {} and "upgrades_downgrades.ToGrade" in fetch_market.EXPECTED_FIELDS
          and "recommendations.To Grade" not in fetch_market.EXPECTED_FIELDS)
    check("format: analyst grades missing for every company now fail the run",
          raises(lambda: fetch_market.check_fields([full(("upgrades_downgrades.ToGrade",))] * 2)))

    # R48 mechanism, with a synthetic exemption: logged while valid; fails the
    # run once MODEL_VERSION reaches its expiry or its field is no longer read.
    real_breaks, real_fields = fetch_market.KNOWN_FORMAT_BREAKS, fetch_market.EXPECTED_FIELDS
    version = fetch_market.MODEL_VERSION
    logged = []
    handler = logging.Handler()
    handler.emit = lambda record: logged.append(record.getMessage())
    fetch_market.log.addHandler(handler)
    try:
        fetch_market.KNOWN_FORMAT_BREAKS = {"info.grossMargins": {"reason": "test", "expires_at": version + 1}}
        ok = not raises(lambda: fetch_market.check_fields([full(("info.grossMargins",))] * 2))
        check("format: a valid exemption is logged as an error on every run, not raised",
              ok and any("Known data-format break: info.grossMargins" in m for m in logged), str(logged))
        fetch_market.KNOWN_FORMAT_BREAKS = {"info.grossMargins": {"reason": "test", "expires_at": version}}
        check("format: an exemption that has reached its model_version fails the run",
              raises(lambda: fetch_market.check_fields([full()] * 2)))
        check("format: ...even when nothing was fetched",
              raises(lambda: fetch_market.check_fields([])))
        fetch_market.KNOWN_FORMAT_BREAKS = {"recommendations.To Grade": {"reason": "test", "expires_at": version + 1}}
        check("format: an exemption for a field the pipeline no longer reads fails the run",
              raises(lambda: fetch_market.check_fields([full()] * 2)))
    finally:
        fetch_market.log.removeHandler(handler)
        fetch_market.KNOWN_FORMAT_BREAKS, fetch_market.EXPECTED_FIELDS = real_breaks, real_fields

    real_rp = fetch_market.run_pipeline
    fetch_market.run_pipeline = lambda *a, **k: (_ for _ in ()).throw(fetch_market.SchemaError("test"))
    try:
        # stage_fetch() checks the calendar against today's date, so the stub's
        # sessions are the two weekdays before today, not fixed dates (a fixed
        # date goes stale after 7 days and the calendar check fails first).
        recent = [d.date().isoformat() for d in
                  pd.bdate_range(end=datetime.date.today() - datetime.timedelta(days=1), periods=2)]
        with_stub(StubTicker(bars(recent)),
                  lambda: main.stage_fetch())
        check("format: stage_fetch lets a data-format failure fail the run", False, "returned normally")
    except fetch_market.SchemaError:
        check("format: stage_fetch lets a data-format failure fail the run", True)
    except RuntimeError as e:
        check("format: stage_fetch lets a data-format failure fail the run", False, f"calendar failed first: {e}")
    finally:
        fetch_market.run_pipeline = real_rp

    class CashStub:
        def __init__(self, cf):
            self.quarterly_cashflow = cf
    cols = pd.to_datetime(["2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30", "2025-06-30"])
    no_row = pd.DataFrame({c: [1.0] for c in cols}, index=["Operating Cash Flow"])
    with_row = pd.DataFrame({c: [-1.0, 1.0] for c in cols}, index=["Capital Expenditure", "Operating Cash Flow"])
    check("format: no hyperscaler cash-flow table with a capex row fails the run",
          raises(lambda: with_stub(lambda symbol: CashStub(no_row), fetch_market.fetch_capex_trend)))
    check("format: one hyperscaler with the capex row is enough",
          not raises(lambda: with_stub(lambda symbol: CashStub(with_row if symbol == "MSFT" else no_row),
                                       fetch_market.fetch_capex_trend)))


def check_r45_inputs():
    """R45: analyst source, momentum, news counting, model_version."""
    fetch = lambda stub: with_stub(stub, lambda: fetch_market.fetch_ticker_data("TST", [], ["cooling"]))

    # 1. Analyst grades: newest-first table; the 10 most recent actions count.
    dates = pd.DatetimeIndex(pd.bdate_range(end="2026-10-09", periods=12)[::-1])     # newest first
    grades = ["Buy", "Hold", "Outperform", "Neutral", "Overweight", "Sell", "Strong Buy", "Hold", "Buy", "Hold",
              "Buy", "Buy"]                                                         # the last two are the oldest
    stub = FullStub(price_bars(130))
    stub.upgrades_downgrades = pd.DataFrame({"Firm": ["X"] * 12, "ToGrade": grades, "FromGrade": [""] * 12,
                                             "Action": ["main"] * 12}, index=dates)
    d = fetch(stub)
    check("analyst: counts buy-side grades among the 10 most recent actions (table sorted first)",
          d["analyst_upgrades"] == 5 and "upgrades_downgrades.ToGrade" in d["_fields_seen"], str(d["analyst_upgrades"]))
    table = stub.upgrades_downgrades
    old = pd.DatetimeIndex(pd.bdate_range(end="2026-09-08", periods=12)[::-1])        # all before the 30 days
    stub.upgrades_downgrades = table.set_axis(old)
    d = fetch(stub)
    check("analyst: actions older than 30 days before the session don't count (a real 0, not missing)",
          d["analyst_upgrades"] == 0 and "analyst_upgrades" not in d["data_missing"], str(d["analyst_upgrades"]))
    later = pd.DatetimeIndex(pd.bdate_range(start="2026-10-12", periods=12)[::-1])    # all after the session
    stub.upgrades_downgrades = table.set_axis(later)
    d = fetch(stub)
    check("analyst: actions dated after the session don't count", d["analyst_upgrades"] == 0, str(d["analyst_upgrades"]))
    class Failing(FullStub):
        @property
        def upgrades_downgrades(self):
            raise ConnectionError("network down")
        @upgrades_downgrades.setter
        def upgrades_downgrades(self, value):
            pass
    d = fetch(Failing(price_bars(130)))
    check("analyst: a failed fetch is missing data (None, named)",
          d["analyst_upgrades"] is None and "analyst_upgrades" in d["data_missing"])
    stub.upgrades_downgrades = table
    stub.upgrades_downgrades = stub.upgrades_downgrades.iloc[0:0]
    d = fetch(stub)
    check("analyst: an empty table is missing data (None, named), not 0",
          d["analyst_upgrades"] is None and "analyst_upgrades" in d["data_missing"])
    stub.upgrades_downgrades = None
    d = fetch(stub)
    check("analyst: no table at all is missing data (None, named), not 0",
          d["analyst_upgrades"] is None and "analyst_upgrades" in d["data_missing"])

    # 2. Momentum.
    def momentum(closes):
        return fetch(FullStub(price_bars(len(closes), closes=closes)))["price_momentum"]
    falling = [200.0 * (0.997 ** i) for i in range(124)] + [200.0 * (0.997 ** 123) * (0.99 ** k) for k in range(1, 7)]
    m = momentum(falling)
    check("momentum: a stock falling faster than its 90-day downtrend is below 1 (old formula: above 1)",
          m is not None and m < 1, str(m))
    flat = [100.0 + (0.3 if i % 2 else -0.3) for i in range(124)] + [100.0, 100.4, 100.8, 101.2, 101.6, 102.0]
    m = momentum(flat)
    check("momentum: a near-flat 90 days doesn't saturate at the +5 limit", m is not None and m < 5, str(m))
    m = momentum([100.0 * (1.004 ** i) for i in range(130)])
    check("momentum: a steady uptrend is exactly 1.0 (in line with its trend)", m == 1.0, str(m))
    faster = [100.0 * (1.004 ** i) for i in range(125)] + [100.0 * (1.004 ** 124) * (1.012 ** k) for k in range(1, 6)]
    m = momentum(faster)
    check("momentum: an uptrend that speeds up in the last 5 sessions is above 1", m is not None and m > 1, str(m))
    m = fetch(FullStub(price_bars(60)))
    check("momentum: fewer than 69 sessions is missing data (None, named)",
          m["price_momentum"] is None and "price_momentum" in m["data_missing"])

    # 3. News counting.
    ctx, brand, tickers = SUB_LAYERS["optical"]["context_keywords"], SUB_LAYERS["optical"]["brand_keywords"], ["CIEN", "GLW"]
    h = lambda src, tk, title, body="": {"source": src, "ticker": tk, "title": title, "text": f"{title} {body}".lower()}
    nv = lambda heads: fetch_market.score_news_velocity(heads, ctx, brand, tickers)
    story = "ciena sold out of 1.6t transceivers"
    check("news: the same story in two feeds of a sub-layer counts once",
          nv([h("ticker", "CIEN", story), h("ticker", "GLW", story)]) == 1.0)
    check("news: a ticker-feed story that doesn't name that company doesn't count",
          nv([h("ticker", "GLW", "lumentum shares jump on optical networking demand")]) == 0.0)
    check("news: a ticker-feed story naming the company with a context term counts 2 points",
          nv([h("ticker", "GLW", "corning expands fiber capacity")]) == 1.0)
    check("news: a generic headline with only a brand name doesn't count",
          nv([h("generic", "", "corning names a new chief financial officer")]) == 0.0)
    check("news: a generic headline with only a shared supply term doesn't count",
          nv([h("generic", "", "boeing's backlog hits a record")]) == 0.0)
    check("news: a generic headline with a sub-layer term counts 1 point",
          nv([h("generic", "", "800g transceiver shipments rise")]) == 0.5)
    check("news: a ticker copy is counted before a generic copy of the same story",
          nv([h("generic", "", story), h("ticker", "CIEN", story)]) == 1.0)

    # 4. model_version on history and audit entries.
    tmp = tempfile.mkdtemp(prefix="r45_mv_")
    cwd, real_file = os.getcwd(), render.SCORES_HISTORY_FILE
    os.chdir(tmp)
    render.SCORES_HISTORY_FILE = "scores_history.json"
    try:
        layers = list(SUB_LAYERS)
        md = {"sub_layers": {lid: [fixture_ticker(lid[:4].upper())] for lid in layers},
              "meta": {"generic_feed_failures": [], "session": "2026-10-06",
                       "sessions": [x.isoformat() for x in SESSIONS if x <= D("2026-10-06")]}}
        macro = {"vix": 18.0, "yield_10y_change": -5.0, "nasdaq_vs_spx_20d": 0.01, "data_missing": []}
        scored = main.stage_score(md, macro)
        render.save_scores_history(scored, "2026-10-06")
        hist = json.load(open("scores_history.json"))
        audit = json.load(open("audit_log.json"))
        from config import MODEL_VERSION
        check("model_version: on every history entry", all(e.get("model_version") == MODEL_VERSION == 2 for e in hist))
        check("model_version: on every audit entry", audit and all(e.get("model_version") == MODEL_VERSION for e in audit))
    finally:
        os.chdir(cwd)
        render.SCORES_HISTORY_FILE = real_file


def check_unfinished_bar():
    h = bars(["2026-10-08", "2026-10-09", "2026-10-12"])
    at = lambda s: datetime.datetime.fromisoformat(s).replace(tzinfo=UTC)
    check("bar: Monday 15:00 ET (19:00 UTC) drops today's bar",
          len(fetch_market.drop_unfinished_bar(h, at("2026-10-12T19:00"))) == 2)
    check("bar: Monday 16:05 ET (20:05 UTC) keeps today's bar",
          len(fetch_market.drop_unfinished_bar(h, at("2026-10-12T20:05"))) == 3)
    h2 = bars(["2026-10-08", "2026-10-09"])
    check("bar: Saturday keeps Friday's bar",
          len(fetch_market.drop_unfinished_bar(h2, at("2026-10-10T10:00"))) == 2)
    h3 = bars(["2026-10-30", "2026-11-02"])
    check("bar: after 1 Nov, 20:30 UTC is 15:30 EST and drops today's bar",
          len(fetch_market.drop_unfinished_bar(h3, at("2026-11-02T20:30"))) == 1)
    check("bar: after 1 Nov, 21:05 UTC is 16:05 EST and keeps today's bar",
          len(fetch_market.drop_unfinished_bar(h3, at("2026-11-02T21:05"))) == 2)

    # R41: a trailing row without a Close goes, whatever its date.
    sat = at("2026-10-10T00:08")                      # the parent's Saturday 00:08 UTC run
    h4 = price_bars(30, end="2026-10-08", trailing_nan=("2026-10-09",))
    kept = fetch_market.drop_unfinished_bar(h4, sat)
    check("bar: a trailing NaN row dated a past session is dropped",
          len(kept) == 30 and kept.index[-1].date() == D("2026-10-08"), str(kept.index[-1].date()))
    h5 = price_bars(30, end="2026-10-09", trailing_nan=("2026-10-12",))
    check("bar: a trailing NaN row dated today is dropped even after the close",
          len(fetch_market.drop_unfinished_bar(h5, at("2026-10-12T20:05"))) == 30)
    h6 = price_bars(30, end="2026-10-07", trailing_nan=("2026-10-08", "2026-10-09"))
    check("bar: two trailing NaN rows are both dropped",
          len(fetch_market.drop_unfinished_bar(h6, sat)) == 30)
    h7 = price_bars(30, nan_at=(-10,))
    check("bar: a NaN in the middle is left for the value checks (only trailing rows go)",
          len(fetch_market.drop_unfinished_bar(h7, sat)) == 30)


def check_sessions_fetch():
    at = datetime.datetime(2026, 10, 12, 19, 0, tzinfo=UTC)      # Monday, 15:00 ET
    s = with_stub(StubTicker(bars(["2026-10-08", "2026-10-09", "2026-10-12"])),
                  lambda: fetch_market.fetch_trading_sessions(at))
    check("sessions: built from ^GSPC bars, today's unfinished bar dropped",
          s == [D("2026-10-08"), D("2026-10-09")], str(s))
    for label, stub in (("raises", StubTicker(exc=ConnectionError("network down"))),
                        ("returns no bars", StubTicker(bars([]))),
                        ("is stale (latest session 10 days old)", StubTicker(bars(["2026-10-01", "2026-10-02"])))):
        try:
            with_stub(stub, lambda: fetch_market.fetch_trading_sessions(at))
            check(f"sessions: a fetch that {label} fails the run", False, "no exception")
        except RuntimeError:
            check(f"sessions: a fetch that {label} fails the run", True)

    reached = []
    real_rp = fetch_market.run_pipeline
    fetch_market.run_pipeline = lambda *a, **k: reached.append(1) or {"sub_layers": {}, "meta": {}}
    try:
        with_stub(StubTicker(exc=ConnectionError("network down")), main.stage_fetch)
        check("stage_fetch: a calendar failure propagates (not swallowed)", False, "returned normally")
    except RuntimeError:
        check("stage_fetch: a calendar failure propagates (not swallowed)", not reached,
              "run_pipeline ran before the failure")
    finally:
        fetch_market.run_pipeline = real_rp


def confirm(score, color, history, current, layer="optical"):
    return main._confirmed_color(score, color, layer, 0.05, history, SESSIONS, D(current))


def check_window():
    # R40: the run for Mon 2026-10-05 never started, so there is no entry at all.
    hist = [entry(d, {"optical": (50.0, "Orange")}) for d in ("2026-09-30", "2026-10-01", "2026-10-02")]
    stored, missing = main._confirmation_window("optical", hist, SESSIONS, D("2026-10-06"))
    check("window: the three sessions before Tue Oct 6 are Oct 1, Oct 2, Oct 5",
          [s for s, _, _ in stored] + missing == [D("2026-10-01"), D("2026-10-02"), D("2026-10-05")])
    check("window: Mon Oct 5 (run never started) is missing, not a score",
          missing == [D("2026-10-05")] and all(sc == 50.0 for _, sc, _ in stored))
    c, note, branch = confirm(50.0, "Orange", hist, "2026-10-06")
    check("note: names the missing day (Mon Oct 5)",
          note == "Orange, confirmed: 2 of 2 available recent sessions also at or above 40 (no reading for Mon Oct 5)", note)
    hist.append(entry("2026-10-05", {"optical": (50.0, "Orange")}))
    c, note, branch = confirm(50.0, "Orange", hist, "2026-10-06")
    check("note: with all three stored, it says 'of the last 3 sessions'",
          note == "Orange, confirmed: 3 of the last 3 sessions also at or above 40", note)

    # A missing day must never count as 0: old code read it as 0 and could confirm Blue.
    hist = [entry("2026-10-01", {"optical": (28.0, "Green")}),
            entry("2026-10-02", {"compute": (40.0, "Green")}),            # optical absent
            entry("2026-10-05", {"optical": (None, "Green")})]            # score missing
    c, note, branch = confirm(20.0, "Blue", hist, "2026-10-06")
    check("missing: an entry without this sub-layer's score is missing, not 0 (no false Blue)",
          branch == main.NO_HISTORY and note == "Latest session only — not yet confirmed "
          "(1 of 2 earlier sessions stored; no reading for Fri Oct 2, Mon Oct 5)", f"{branch}: {note}")

    # Thanksgiving: the market is closed on Thu Nov 26, so it isn't expected.
    hist = [entry(d, {"optical": (35.0, "Green")}) for d in ("2026-11-24", "2026-11-25", "2026-11-27")]
    stored, missing = main._confirmation_window("optical", hist, SESSIONS, D("2026-11-30"))
    check("holiday: Thanksgiving isn't reported missing",
          not missing and [s for s, _, _ in stored] == [D("2026-11-24"), D("2026-11-25"), D("2026-11-27")])
    c, note, branch = confirm(35.0, "Green", hist, "2026-11-30")
    check("holiday: no 'no reading' text in the note", "no reading" not in note, note)

    # History began on Oct 5: Oct 2 predates it and isn't a gap.
    hist = [entry(d, {"optical": (35.0, "Green")}) for d in ("2026-10-05", "2026-10-06")]
    stored, missing = main._confirmation_window("optical", hist, SESSIONS, D("2026-10-07"))
    check("start: sessions before the first stored entry aren't missing", not missing and len(stored) == 2)
    hist = [entry(d, {"optical": (50.0, "Orange")}) for d in ("2026-10-05", "2026-10-06")]
    c, note, branch = confirm(50.0, "Orange", hist, "2026-10-07")
    check("start: with only 2 stored, it says 'of 2 available recent sessions' and names nothing",
          note == "Orange, confirmed: 2 of 2 available recent sessions also at or above 40", note)
    hist = [entry(d, {"optical": (35.0, "Green")}) for d in ("2026-10-01", "2026-10-02")]
    c, note, branch = confirm(38.0, "Green", hist, "2026-10-06")
    check("note: holding says 'latest score' and names the missing day",
          note == "Kept Green: latest score 38.0 isn't confirmed yet, and recent sessions were mostly Green "
          "(no reading for Mon Oct 5)", note)
    hist = [entry(d, {"optical": (20.0, "Blue")}) for d in ("2026-10-01", "2026-10-02")]
    c, note, branch = confirm(52.0, "Orange", hist, "2026-10-06")
    check("note: not sustained says 'latest score' and names the missing day",
          note == "Shown as Orange: latest score 52.0 hasn't held over recent sessions (no reading for Mon Oct 5)", note)
    stored, missing = main._confirmation_window("optical", [], SESSIONS, D("2026-10-07"))
    check("start: an empty history names no missing days", not stored and not missing)

    # R63: steady Green, judged on the stored (shown) colour, not the score band.
    hist = [entry(d, {"optical": (35.0, "Green")}) for d in ("2026-10-01", "2026-10-02", "2026-10-05")]
    c, note, branch = confirm(38.0, "Green", hist, "2026-10-06")
    check("steady: Green now and in all 3 stored sessions reads 'Green, steady'",
          (c, note, branch) == ("Green", "Green, steady: also Green in the last 3 sessions", "steady"), f"{branch}: {note}")
    hist[1] = entry("2026-10-02", {"optical": (35.0, "Orange")})     # Green-band score, but shown Orange (held)
    c, note, branch = confirm(38.0, "Green", hist, "2026-10-06")
    check("steady: a session shown in another colour (score in the Green band) keeps the holding note",
          branch == "holding" and note.startswith("Kept Green: latest score 38.0 isn't confirmed yet"), f"{branch}: {note}")
    hist = [entry(d, {"optical": (35.0, "Green")}) for d in ("2026-10-01", "2026-10-02")]
    c, note, branch = confirm(38.0, "Green", hist, "2026-10-06")
    check("steady: with a session missing, the holding note stays (names the missing day)",
          branch == "holding" and note.endswith("(no reading for Mon Oct 5)"), f"{branch}: {note}")

    # 7-day limit: after an exceptional closure, older entries don't count.
    gap_sessions = [D("2026-09-30"), D("2026-10-01"), D("2026-10-12")]
    hist = [entry(d, {"optical": (50.0, "Orange")}) for d in ("2026-09-30", "2026-10-01", "2026-10-12")]
    stored, missing = main._confirmation_window("optical", hist, gap_sessions, D("2026-10-13"))
    check("age: entries more than 7 calendar days old don't count",
          [s for s, _, _ in stored] == [D("2026-10-12")] and not missing)

    # A second run in the same session must not count its own earlier entry.
    hist = [entry(d, {"optical": (50.0, "Orange")}) for d in ("2026-10-07", "2026-10-08", "2026-10-09")]
    stored, missing = main._confirmation_window("optical", hist, SESSIONS, D("2026-10-09"))
    check("re-run: the current session's own entry isn't a previous day",
          D("2026-10-09") not in [s for s, _, _ in stored])


def check_loader(tmp):
    path = os.path.join(tmp, "history_loader.json")
    render.SCORES_HISTORY_FILE = path
    ci = os.environ.get("GITHUB_ACTIONS")
    try:
        for label, content in (("unreadable", "{not json"), ("of an unexpected type", "42")):
            open(path, "w").write(content)
            os.environ["GITHUB_ACTIONS"] = "true"
            try:
                render.load_scores_history()
                check(f"loader: a history file that is {label} fails the run in CI", False, "no exception")
            except RuntimeError:
                check(f"loader: a history file that is {label} fails the run in CI", True)
            os.environ.pop("GITHUB_ACTIONS")
            check(f"loader: locally, a history file that is {label} is treated as empty",
                  render.load_scores_history() == [])
        os.remove(path)
        os.environ["GITHUB_ACTIONS"] = "true"
        check("loader: a missing file is an empty history (restore failures are the persist step's job)",
              render.load_scores_history() == [])
        os.environ.pop("GITHUB_ACTIONS")

        scored = {"optical": {"best": {"score": 50.0, "color": "Orange"}, "all_tickers": []}}
        render.save_scores_history(scored, "2026-10-09")
        render.save_scores_history(scored, "2026-10-09")
        saved = render.load_scores_history()
        check("save: entries are dated by session and a re-run replaces the earlier one",
              [e["date"] for e in saved] == ["2026-10-09"] and "run_at" in saved[0], str(saved))
    finally:
        if ci is None:
            os.environ.pop("GITHUB_ACTIONS", None)
        else:
            os.environ["GITHUB_ACTIONS"] = ci


def check_audit_log(tmp):
    """R33c: one audit entry per ticker per session, no cap, inputs and model_version on each."""
    import score_engine
    from config import MODEL_VERSION
    folder = os.path.join(tmp, "audit")
    os.makedirs(folder, exist_ok=True)
    cwd, ci = os.getcwd(), os.environ.get("GITHUB_ACTIONS")
    os.chdir(folder)
    macro = {"vix": 18.0, "yield_10y_change": -5.0, "nasdaq_vs_spx_20d": 0.01, "data_missing": []}
    layers = list(SUB_LAYERS)

    def score(session, extra=()):
        md = {"sub_layers": {lid: [fixture_ticker(lid[:4].upper())] + [t for t in extra if lid == "optical"]
                             for lid in layers},
              "meta": {"generic_feed_failures": [], "session": session,
                       "sessions": [x.isoformat() for x in SESSIONS if x <= D(session)]}}
        main.stage_score(md, macro)
        return json.load(open("audit_log.json", encoding="utf-8"))

    try:
        blind = dict(fixture_ticker("BLND"), growth_curr=None, growth_prev=None, gm_delta=None)
        a = score("2026-10-06", extra=(blind,))
        keys = {"session", "run_at", "sub_layer", "ticker", "score", "accel", "constraints", "smart",
                "fund_delta", "missing_fields", "model_version"}
        check("audit: one entry per ticker for the session, each with its inputs and model_version",
              len(a) == len(layers) + 1 and all(keys <= set(e) and e["session"] == "2026-10-06"
                                                and e["model_version"] == MODEL_VERSION for e in a), str(a[:1]))
        check("audit: each entry names its ticker and sub-layer",
              sorted(e["ticker"] for e in a) == sorted([lid[:4].upper() for lid in layers] + ["BLND"])
              and all(e["sub_layer"] in layers for e in a))
        b = [e for e in a if e["ticker"] == "BLND"]
        check("audit: a ticker with insufficient data still gets its entry (score None, missing fields named)",
              len(b) == 1 and b[0]["score"] is None and b[0]["missing_fields"], str(b))
        a = score("2026-10-06")
        check("audit: a re-run within the session replaces its tickers' entries, not appends",
              sum(e["ticker"] != "BLND" for e in a) == len(layers) and len(a) == len(layers) + 1, f"{len(a)} entries")
        a = score("2026-10-07")
        check("audit: the next session adds its own entries; the earlier session's stay",
              sorted({e["session"] for e in a}) == ["2026-10-06", "2026-10-07"] and len(a) == 2 * len(layers) + 1,
              f"{len(a)} entries")
        old = [{"session": "2025-01-02", "ticker": f"T{k}", "sub_layer": "optical"} for k in range(600)]
        json.dump(old, open("audit_log.json", "w", encoding="utf-8"))
        a = score("2026-10-08")
        check("audit: no cap (600 earlier entries are all kept)", len(a) == 600 + len(layers), f"{len(a)} entries")
        open("audit_log.json", "w").write("{not json")
        os.environ["GITHUB_ACTIONS"] = "true"
        try:
            score("2026-10-08")
            check("audit: an unreadable audit log fails the run in CI", False, "no exception")
        except RuntimeError:
            check("audit: an unreadable audit log fails the run in CI", True)
        os.environ.pop("GITHUB_ACTIONS")
        a = score("2026-10-08")
        check("audit: locally, an unreadable audit log is replaced", len(a) == len(layers))
    finally:
        os.chdir(cwd)
        if ci is None:
            os.environ.pop("GITHUB_ACTIONS", None)
        else:
            os.environ["GITHUB_ACTIONS"] = ci


def check_workflow():
    """R33a: the deploy workflow restores the history and audit log from the data branch, and only a
    separate save job may write (contents: write) to push them back. Plain-text parsing (no YAML library)."""
    text = open(os.path.join(REPO, ".github", "workflows", "deploy.yml"), encoding="utf-8").read()
    jobs_at = text.index("\njobs:\n")
    top, jobs = text[:jobs_at], text[jobs_at:]
    blocks = dict(re.findall(r"^  ([\w-]+):\n((?:    .*\n|[ \t]*\n)+)", jobs, re.M))
    build, save, report = blocks.get("build-and-deploy", ""), blocks.get("save-history", ""), blocks.get("report-failure", "")
    check("workflow: the workflow-wide token can only read contents",
          re.search(r"\npermissions:\n(  .*\n)*  contents: read", top) is not None)
    check("workflow: the build-and-deploy job never gets contents: write", "contents: write" not in build)
    restore = build.find("git show origin/data:scores_history.json")
    run = build.find("python main.py --now")
    check("workflow: the build restores both files from the data branch before the pipeline runs",
          0 < restore < run and "git show origin/data:audit_log.json" in build, f"restore at {restore}, pipeline at {run}")
    check("workflow: the build hands both files on as an artifact",
          re.search(r"upload-artifact@v\d[\s\S]*?scores_history\.json[\s\S]*?audit_log\.json", build) is not None)
    check("workflow: only the save job has contents: write, and it runs after the build",
          "contents: write" in save and re.search(r"needs: \[?build-and-deploy", save) is not None
          and text.count("contents: write") == 1)
    check("workflow: the save job pushes to the data branch", "git push origin HEAD:data" in save)
    check("workflow: a failed save opens the failure issue too",
          re.search(r"needs: \[[^\]]*save-history[^\]]*\]", report) is not None and "if: failure()" in report)


def fixture_ticker(symbol):
    return {"ticker": symbol, "name": f"{symbol} test company", "price": 100.0, "currency": "USD",
            "growth_curr": 0.30, "growth_prev": 0.25, "gm_delta": 0.01, "gross_margin": 0.40,
            "news_velocity": 4.0, "capex_div": 0.30, "vol_spike": 1.10, "price_act": 0.01,
            "analyst_upgrades": 0, "short_int_change": 0.0, "price_30d_return": 0.05,
            "price_history": [100.0 + i for i in range(30)], "week52_high": 120.0, "week52_low": 80.0,
            "price_history_dates": [d.date().isoformat() for d in pd.bdate_range(end="2026-10-06", periods=30)],
            "market_cap": 1e11, "revenue_quarterly": None, "price_momentum": 1.5,
            "peer_outperformance": 0.0, "analyst_count": 10, "sector": "Technology",
            "data_date": "2026-10-06", "data_missing": []}


def check_rendered_note(tmp, shots):
    """End to end: stage_score() -> generate_dashboard(), with Mon Oct 5 never run."""
    os.chdir(tmp)
    render.SCORES_HISTORY_FILE = "scores_history.json"
    layers = list(SUB_LAYERS)
    history = [entry(d, {lid: (50.0, "Orange") for lid in layers})
               for d in ("2026-09-30", "2026-10-01", "2026-10-02")]
    json.dump(history, open("scores_history.json", "w"))
    market_data = {"sub_layers": {lid: [fixture_ticker(lid[:4].upper())] for lid in layers},
                   "meta": {"generic_feed_failures": [],
                            "session": "2026-10-06",
                            "sessions": [s.isoformat() for s in SESSIONS if s <= D("2026-10-06")]}}
    macro = {"vix": 18.0, "yield_10y_change": -5.0, "nasdaq_vs_spx_20d": 0.01, "data_missing": []}
    scored = main.stage_score(market_data, macro)
    render.generate_dashboard(scored, macro, market_data, None)
    html = open("index.html", encoding="utf-8").read()
    js = json.loads(re.search(r"const LAYERS\s*=\s*(\[.*?\]);\nconst HISTORY", html, re.S).group(1))
    notes = {l["id"]: l.get("note", "") for l in js}
    check("page: every sub-layer card's note names Mon Oct 5",
          all("no reading for Mon Oct 5" in n for n in notes.values()), json.dumps(notes))
    print("     card notes on the rendered page:")
    for lid, n in notes.items():
        print(f"       {lid:<11} {n}")
    saved = json.load(open("scores_history.json"))
    check("page: this run's entry is dated by session (2026-10-06)", saved[-1]["date"] == "2026-10-06")
    check("page: no NaN anywhere on the rendered page", "NaN" not in html)
    check("page: the score delta is labelled with the comparison session (Fri Oct 2), never 'yesterday'",
          'const PREV_LABEL   = "Fri Oct 2";' in html and "vs yesterday" not in html)
    m = re.search(r"Data: close of Tue Oct 6 · fetched \d\d:\d\d UTC · Quarterly financials", html)
    check("page: the data line names the session the scores belong to", m is not None)
    check("page: each price carries its session date",
          all(t.get("price_date") == "Tue Oct 6" for l in js for t in l.get("tickers", [])))
    check("page: the header gives the run time in UTC",
          re.search(r'<div class="hero-sub">\w+, \w+ \d\d \d{4} · \d\d:\d\d UTC</div>', html) is not None)
    check("page: sparkline labels are each point's session date, ending at the session (Oct 6)",
          all(t.get("spark_dates", [])[-1:] == ["Oct 6"] and len(t["spark_dates"]) == len(t["sparkline"])
              for l in js for t in l.get("tickers", []))
          and "new Date()" not in html, str([t.get("spark_dates", [])[-2:] for l in js for t in l.get("tickers", [])][:1]))

    if shots:
        from playwright.sync_api import sync_playwright
        os.makedirs(shots, exist_ok=True)
        out = os.path.join(shots, "scores-card-missing-day-1680.png")
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1680, "height": 1050})
            pg.goto("file:///" + os.path.join(tmp, "index.html").replace("\\", "/"))
            pg.wait_for_selector("#chain .layer")
            pg.locator("#chain .layer").first.click()          # open one card's detail (price row)
            pg.locator(".card").first.screenshot(path=out)
            b.close()
        print(f"     screenshot: {out}")

    # No history at all (as in CI today): the page line and the no-history note.
    os.remove("scores_history.json")
    scored = main.stage_score(market_data, macro)
    render.generate_dashboard(scored, macro, market_data, None)
    html = open("index.html", encoding="utf-8").read()
    js = json.loads(re.search(r"const LAYERS\s*=\s*(\[.*?\]);\nconst HISTORY", html, re.S).group(1))
    check("page, no history: the page line uses the session wording",
          "Colours are based on the latest session's reading only; multi-day confirmation starts once "
          "a few sessions of history are stored." in html)
    check("page, no history: every note says 'Latest session only' and names nothing",
          all(l.get("note") == "Latest session only — not yet confirmed (0 of 2 earlier sessions stored)" for l in js),
          json.dumps([l.get("note") for l in js]))


def check_regime_label(tmp):
    """R71: the page's market-regime label is the regime and multiplier the engine applied, for
    the cases where the old render.py rule disagreed (VIX alone) and the edges (two risk signals,
    nothing usable). Rendered end to end through stage_score() and generate_dashboard()."""
    from score_engine import ScoreEngine
    work = os.path.join(tmp, "regime")
    os.makedirs(work, exist_ok=True)
    os.chdir(work)
    render.SCORES_HISTORY_FILE = "scores_history.json"
    layers = list(SUB_LAYERS)
    market_data = {"sub_layers": {lid: [fixture_ticker(lid[:4].upper())] for lid in layers},
                   "meta": {"generic_feed_failures": [], "session": "2026-10-06",
                            "sessions": [s.isoformat() for s in SESSIONS if s <= D("2026-10-06")]}}
    cases = [("VIX 25 alone", {"vix": 25.0, "yield_10y_change": None, "nasdaq_vs_spx_20d": None},
              "Market regime: Risk-On · scores × 1.00"),
             ("VIX 35 alone", {"vix": 35.0, "yield_10y_change": None, "nasdaq_vs_spx_20d": None},
              "Market regime: Neutral · scores × 0.85"),
             ("VIX 35 + yield +120 bps", {"vix": 35.0, "yield_10y_change": 120.0, "nasdaq_vs_spx_20d": None},
              "Market regime: Risk-Off · scores × 0.65"),
             ("all three missing", {"vix": None, "yield_10y_change": None, "nasdaq_vs_spx_20d": None},
              "Market regime: Unknown (macro data unavailable)")]
    for name, macro, want in cases:
        if os.path.exists("scores_history.json"):
            os.remove("scores_history.json")
        macro = dict(macro, data_missing=[])
        scored = main.stage_score(market_data, macro)
        render.generate_dashboard(scored, macro, market_data, None)
        page = open("index.html", encoding="utf-8").read()
        m = re.search(r'<div class="reg-pill" tabindex="0">(.*?)\n\s*<div class="reg-tooltip">', page, re.S)
        shown = m.group(1).strip() if m else None
        mult, regime = ScoreEngine(macro).get_macro_multiplier([])
        used = {(t["regime"], t["multiplier"]) for l in scored.values() for t in (l.get("all_tickers") or [])}
        check(f"regime label, {name}: the page shows the regime the scores used ({want})",
              shown == want and want.startswith("Market regime: " + regime)
              and (used == {(regime, mult)} or regime.startswith("Unknown")), f"{shown!r}, engine {regime} x{mult}, used {used}")
    check("regime label: the tooltip states the voting rule the engine applies",
          "<b>Rule applied:</b> Risk-Off (scores × 0.65) needs two risk signals" in page and "A missing signal doesn't vote." in page)


def check_dashboard_page(tmp):
    """R59 items 2 and 5, in a browser on the page check_rendered_note() rendered: the section heading,
    the card anchors (index.html#layer-<id> opens that card) and the family link cards' style."""
    from playwright.sync_api import sync_playwright
    url = "file:///" + os.path.join(tmp, "index.html").replace("\\", "/")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1680, "height": 1050})
        pg.goto(url + "#layer-optical"); pg.wait_for_timeout(400)
        st = pg.evaluate("""() => { const h = document.querySelector('.section-heading'), c = h && getComputedStyle(h);
            const card = document.getElementById('layer-optical'), r = card && card.getBoundingClientRect();
            return {heading: h && [h.tagName, h.textContent, c.fontSize, c.fontWeight, c.color, h.getAttribute('style')],
                    ids: [...document.querySelectorAll('#chain .layer')].map(e => e.id), active,
                    inView: !!r && r.top >= 0 && r.bottom <= innerHeight,
                    expanded: (document.getElementById('expand-area').textContent || '')
                              .includes(LAYERS.find(l => l.id === 'optical').tickers[0].sym),
                    links: [...document.querySelectorAll('.family-link')].map(a => ({href: a.getAttribute('href'), cls: a.className,
                            open: (a.querySelector('.fl-open') || {}).textContent, tag: (a.querySelector('.fl-tag') || {}).textContent || null,
                            tile: getComputedStyle(a.querySelector('.fl-icon')).backgroundColor}))} }""")
        check("heading: 'Data center infrastructure — signal scores' is an h2 in dark navy, 20px, bold, styled in CSS",
              st["heading"] == ["H2", "Data center infrastructure — signal scores", "20px", "700", "rgb(14, 22, 40)", None],
              str(st["heading"]))
        check("anchors: every sub-layer card has the id layer-<id>",
              st["ids"] == [f"layer-{lid}" for lid in SUB_LAYERS], str(st["ids"]))
        check("anchors: index.html#layer-optical opens the optical card, in view, with its companies",
              st["active"] == "optical" and st["inView"] and st["expanded"], str({k: st[k] for k in ("active", "inView", "expanded")}))
        pg.evaluate("location.hash = '#layer-colocation'"); pg.wait_for_timeout(300)
        check("anchors: changing the hash opens that card", pg.evaluate("active") == "colocation")
        links = st["links"]
        check("link cards: ecosystem map and the Finnish explainer, each with an 'Open →' pill and a coloured icon tile",
              [l["href"] for l in links] == ["ecosystem.html", "business-models/"]
              and all(l["open"] == "Open →" and l["tile"] not in ("rgba(0, 0, 0, 0)", "transparent") for l in links), str(links))
        check("link cards: the explainer card in its cream-and-navy editorial style with an FI tag",
              "fl-editorial" in links[1]["cls"] and links[1]["tag"] == "FI" and "fl-editorial" not in links[0]["cls"], str(links))
        # R63 item 3: the ticker rows say what the arrow and the percentage are.
        tk = pg.evaluate("""() => ({key: (document.querySelector('.trend-key') || {}).textContent,
            vals: [...document.querySelectorAll('#chain .lyr-tk')].map(r => r.lastElementChild.textContent.trim()),
            tips: [...document.querySelectorAll('#chain .tk-arrow')].map(a => [a.textContent, a.title, a.getAttribute('aria-label')]),
            bands: LAYERS.flatMap(l => l.tickers.slice(0, 3).map(t => t.delta_band)),
            exLabels: [...document.querySelectorAll('#expand-area .ex-lbl')].map(e => e.textContent)})""")
        check("ticker rows: the key line explains the arrow and the 30-day percentage",
              tk["key"] == "▲ ▼ — revenue growth speeding up / slowing / steady · 30d = share price change over 30 days", str(tk["key"]))
        check("ticker rows: every percentage is labelled 30d", tk["vals"] and all(v.startswith("30d ") for v in tk["vals"]), str(tk["vals"]))
        tips = pg.evaluate("TREND_TIP")
        check("ticker rows: each arrow carries its revenue-growth tooltip (title and screen-reader label), in percentage points",
              tk["tips"] and all(t[1] == t[2] == tips[b] for t, b in zip(tk["tips"], tk["bands"]))
              and all("percentage points" in tips[k] for k in ("accelerating", "decelerating", "stable"))
              and tips["accelerating"].startswith("Revenue growth speeding up: year-on-year growth in the latest quarter is more than 5 percentage points above"),
              str(tk["tips"][:2]))
        # R63 item 4: trend words in the chain bar only when stored history backs the colours.
        strip = pg.evaluate("""() => {
          const L = (id, n1, score, color) => ({id, n1, score, color, insufficient: false, tickers: []});
          const run = (layers, confirmed) => { buildBottleneckStrip(layers, confirmed);
            return document.getElementById('bottleneck-strip').innerText.replace(/\\s+/g, ' ').trim(); };
          const green = [L('a', 'Optical', 44, 'Green'), L('b', 'Cooling', 38, 'Green'), L('c', 'Colocation', 27.4, 'Green')];
          const out = {noHistory: run(green, false), allGreen: run(green, true),
            all: run([L('a', 'Optical', 70, 'Red'), L('b', 'Cooling', 50, 'Orange'), L('c', 'Colocation', 20, 'Blue')], true),
            orange: run([L('a', 'Optical', 50, 'Orange'), L('c', 'Colocation', 30, 'Green')], true),
            blue: run([L('a', 'Optical', 40, 'Green'), L('c', 'Colocation', 20, 'Blue')], true),
            redNoHistory: run([L('a', 'Optical', 70, 'Red'), L('c', 'Colocation', 20, 'Blue')], false),
            pageConfirmed: CONFIRMED_HISTORY};
          out.page = run(LAYERS, CONFIRMED_HISTORY);
          return out }""")
        check("chain bar: before confirmation has history it names scores: 'Highest score: … · Lowest score: …' (even with Red/Blue)",
              strip["noHistory"] == "Highest score: Optical (44) · Lowest score: Colocation (27)"
              and strip["redNoHistory"] == "Highest score: Optical (70) · Lowest score: Colocation (20)", str(strip))
        check("chain bar: with history but no confirmed Red, Orange or Blue, the same two scores",
              strip["allGreen"] == "Highest score: Optical (44) · Lowest score: Colocation (27)", strip["allGreen"])
        check("chain bar: confirmed Red, Orange and Blue keep Bottleneck, Emerging and Easing",
              strip["all"] == "Bottleneck: Optical → Emerging: Cooling → Easing: Colocation", strip["all"])
        check("chain bar: no Red or Orange -> 'Highest score' at the top end; no Blue -> 'Lowest score' at the bottom end",
              strip["orange"] == "Emerging: Optical → Lowest score: Colocation (30)"
              and strip["blue"] == "Highest score: Optical (40) → Easing: Colocation", f"{strip['orange']} | {strip['blue']}")
        check("chain bar: this page (no stored history) shows the scores version",
              strip["pageConfirmed"] is False and strip["page"].startswith("Highest score:") and " · Lowest score:" in strip["page"],
              strip["page"])
        check("ticker rows: the expanded card labels the trend 'Revenue growth', next to '30d return'",
              "Revenue growth" in tk["exLabels"] and "Trend" not in tk["exLabels"] and "30d return" in tk["exLabels"], str(tk["exLabels"]))
        b.close()


def run(shots):
    cwd = os.getcwd()
    tmp = tempfile.mkdtemp(prefix="check_confirmation_")
    real_file = render.SCORES_HISTORY_FILE
    try:
        check_unfinished_bar()
        check_sessions_fetch()
        check_window()
        check_nan_values()
        check_session_prices()
        check_data_format()
        check_r45_inputs()
        check_loader(tmp)
        check_audit_log(tmp)
        check_workflow()
        check_rendered_note(tmp, shots)
        check_dashboard_page(tmp)
        check_regime_label(tmp)
    finally:
        os.chdir(cwd)
        render.SCORES_HISTORY_FILE = real_file
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", help="folder for a PNG of the rendered cards (needs Playwright)")
    a = ap.parse_args()
    shots = os.path.abspath(a.shots) if a.shots else None
    sys.exit(run(shots))

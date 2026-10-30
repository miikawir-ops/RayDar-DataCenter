"""Checks for revenue growth (PLAN.md ledger R88 step 1): growth is
year-over-year, a quarter against the quarter ending ~a year earlier,
matched by date. Acceleration (growth delta) is the change in that YoY
between the latest two quarters, so it needs 6 quarters; with fewer it's
unmeasured (None), never estimated from EPS growth.

The old code took dropna() columns 0,1,2,3 as q0,q1,q4,q5, i.e. compared the
latest quarter with the one 2 quarters back, and growth_prev fell back to
info's earningsGrowth (EPS growth). Ported from the parent's
test_revenue_growth.py. Offline: yfinance and EDGAR are stubbed.

Run: python tools/check_revenue_growth.py   (exit 0 when every check passes)
"""
import os
import sys
import math
import logging
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fetch_market  # noqa: E402

results = []
NAN = float("nan")


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


class FakeTicker:
    def __init__(self, revenue, **info):
        dates = pd.bdate_range(end="2026-10-23", periods=80)
        n = len(dates)
        self.info = {"marketCap": 1e11, "currentPrice": 100.0, "grossMargins": 0.5, **info}
        self._bars = pd.DataFrame({"Close": [100.0] * n, "Adj Close": [100.0] * n, "High": [101.0] * n,
                                   "Low": [99.0] * n, "Volume": [1e6] * n}, index=dates)
        self.quarterly_financials = pd.DataFrame(
            {pd.Timestamp(k): [v * 1e9] for k, v in revenue.items()}, index=["Total Revenue"])
        self.quarterly_cashflow = pd.DataFrame()
        self.upgrades_downgrades = pd.DataFrame()

    def history(self, **kw):
        return self._bars


def fetch(revenue, edgar_rev=None, **info):
    """revenue: {quarter_end: $bn}, newest first as yfinance orders it."""
    edgar_ret = ({pd.Timestamp(k).date(): v * 1e9 for k, v in edgar_rev.items()}, "us-gaap:Revenues [USD]") \
        if edgar_rev else (None, "off in this check")
    with patch("fetch_market.yf.Ticker", return_value=FakeTicker(revenue, **info)), \
         patch("edgar.quarterly_revenue", return_value=edgar_ret):
        return fetch_market.fetch_ticker_data("TST", [], ["x"], layer_tickers=["TST"])


def check_true_yoy():
    # MU's real yfinance revenue on 2026-10-24 ($bn), the parent's case: latest column NaN.
    mu = {"2026-08-31": NAN, "2026-05-31": 41.456, "2026-02-28": 23.86,
          "2025-11-30": 13.643, "2025-08-31": 11.315, "2025-05-31": 9.301}
    r = fetch(mu, earningsGrowth=9.99)
    want = round(41.456 / 9.301 - 1, 4)
    check("growth is date-matched YoY, not 2 quarters back (old code: 2.0386)",
          r["growth_curr"] is not None and math.isclose(r["growth_curr"], want, abs_tol=1e-4), r["growth_curr"])
    check("growth_quarter names the quarter-end", r["growth_quarter"] == "2026-05-31", r["growth_quarter"])
    check("with 5 quarters, acceleration is unmeasured, not EPS growth (old code: earningsGrowth)",
          r["growth_prev"] is None and "growth_prev" in r["data_missing"], (r["growth_prev"], r["data_missing"]))


def check_six_quarters():
    six = {"2026-06-30": 15.0, "2026-03-31": 13.0, "2025-12-31": 12.0,
           "2025-09-30": 11.0, "2025-06-30": 10.0, "2025-03-31": 10.0}
    r = fetch(six)
    check("6 quarters give YoY for the latest two quarters (+50%, +30%)",
          math.isclose(r["growth_curr"], 0.5, abs_tol=1e-4) and math.isclose(r["growth_prev"], 0.3, abs_tol=1e-4),
          (r["growth_curr"], r["growth_prev"]))


def check_edgar_fill():
    # DLR's case (2026-10-28): yfinance's newest column empty; EDGAR has it and older quarters.
    yf_q = {"2026-06-30": NAN, "2026-03-31": 1.6352, "2025-12-31": 1.6347, "2025-09-30": 1.5772,
            "2025-06-30": 1.4932, "2025-03-31": 1.4076}
    ed = {"2026-06-30": 1.70, "2026-03-31": 1.6352, "2025-12-31": 1.6347, "2025-09-30": 1.5772,
          "2025-06-30": 1.4932, "2025-03-31": 1.4076, "2024-12-31": 1.4355, "2024-09-30": 1.4300}
    r = fetch(yf_q, edgar_rev=ed)
    check("EDGAR supplies the quarter yfinance leaves blank (growth_quarter 2026-06-30)",
          r["growth_quarter"] == "2026-06-30", r["growth_quarter"])
    check("acceleration measured from the EDGAR-filled series",
          r["growth_prev"] is not None and math.isclose(r["growth_prev"], round(1.6352 / 1.4076 - 1, 4), abs_tol=1e-4),
          r["growth_prev"])
    check("revenue_source names EDGAR", r["revenue_source"].startswith("yfinance + EDGAR"), r["revenue_source"])


def run():
    logging.disable(logging.CRITICAL)
    check_true_yoy()
    check_six_quarters()
    check_edgar_fill()
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())

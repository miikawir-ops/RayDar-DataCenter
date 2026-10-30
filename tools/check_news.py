"""Checks for per-ticker news (PLAN.md ledger R88 steps 4-5): run_pipeline()
scores each ticker's news on its own feed. It passed the whole sub-layer's
ticker list into the ownership filter, so every ticker in a sub-layer got
the same pooled score (2026-10-29 live headlines: optical 7.0 for all four,
3.0 / 0.0 / 3.0 / 1.0 per ticker). The parent's c74acc1. Offline: feeds,
yfinance and EDGAR are stubbed; files go to a temporary folder.

Run: python tools/check_news.py   (exit 0 when every check passes)
"""
import os
import sys
import logging
import tempfile
from unittest.mock import patch

import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import fetch_market  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


class FakeTicker:
    def __init__(self, *a, **k):
        dates = pd.bdate_range(end="2026-10-23", periods=80)
        self.info = {"marketCap": 1e11, "currentPrice": 100.0}
        self._bars = pd.DataFrame({c: [100.0] * len(dates) for c in ("Close", "Adj Close", "High", "Low", "Volume")},
                                  index=dates)
        self.quarterly_financials = self.quarterly_cashflow = self.upgrades_downgrades = pd.DataFrame()

    def history(self, **kw):
        return self._bars


def check_per_ticker():
    # One Arista story with a networking term in Arista's own feed; nothing for Cisco.
    headlines = [{"text": "arista wins ai networking orders", "title": "arista wins ai networking orders",
                  "ticker": "ANET", "source": "ticker"}]
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            with patch("fetch_market.fetch_all_headlines", return_value=(headlines, set(), [])), \
                 patch("fetch_market.yf.Ticker", FakeTicker), \
                 patch("fetch_market.check_fields", lambda t: None):
                out = fetch_market.run_pipeline()
        finally:
            os.chdir(cwd)
    news = {t["ticker"]: t["news_velocity"] for t in out["sub_layers"]["networking"]}
    check("Arista's story counts for Arista", news.get("ANET") == 1.0, news)
    check("Cisco's news is its own, not Arista's (old code: 1.0, pooled)", news.get("CSCO") == 0.0, news)


def check_layer_badge():
    """Step 5: the sub-layer's news number is the best ticker's own, the same
    company whose fund_delta the divergence text uses, not the first ticker's."""
    import json
    import render
    first = {"ticker": "ANET", "score": 40.0, "color": "Green", "fund_delta": 0.01, "news_velocity": 0.0}
    best  = {"ticker": "CSCO", "score": 60.0, "color": "Green", "fund_delta": 0.01, "news_velocity": 6.0}
    scored = {"networking": {"best": dict(best), "all_tickers": [first, best], "tickers_scored": 2, "tickers_total": 2}}
    layers = json.loads(render._chain_js_data(scored, {"sub_layers": {}}, {}))
    l = layers[0]
    check("the sub-layer news number is the best ticker's own (old code: the first ticker's 0.0)",
          l["news_vel"] == 6.0, l["news_vel"])
    check("the divergence text reads that same company's news", l["divergence"] is True, (l["divergence"], l["divergence_msg"]))


def run():
    logging.disable(logging.CRITICAL)
    check_per_ticker()
    check_layer_badge()
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())

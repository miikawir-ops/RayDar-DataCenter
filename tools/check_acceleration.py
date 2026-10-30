"""Checks for unmeasured revenue acceleration (PLAN.md ledger R88 steps 3 and 6):
with growth_prev missing, the growth delta is unknown, and an unknown delta
is never treated as an accelerating one. It gets no high-margin bonus, no
company is Red on it, and no sub-layer reaches Red (instant, confirmed or
held) unless at least one of its companies has a measured delta. The
parent's rules. Offline; files go to a temporary folder.

Run: python tools/check_acceleration.py   (exit 0 when every check passes)
"""
import os
import sys
import json
import logging
import tempfile
from unittest.mock import patch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from score_engine import ScoreEngine  # noqa: E402
from config import SUB_LAYERS         # noqa: E402
import main                            # noqa: E402
import render                          # noqa: E402

results = []
MACRO = {"vix": 18.0, "yield_10y_change": -5.0, "nasdaq_vs_spx_20d": 0.01, "data_missing": []}


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def ticker(sym, **kw):
    t = {"ticker": sym, "name": sym, "price": 100.0, "growth_curr": 0.60, "growth_prev": None, "gm_delta": 0.02,
         "gross_margin": 0.60, "news_velocity": 4.0, "capex_div": 0.30, "vol_spike": 1.1, "price_act": 0.01,
         "analyst_upgrades": 2, "short_int_change": 0.0, "price_30d_return": 0.05, "price_momentum": 1.5,
         "peer_outperformance": 0.0, "market_cap": 1e11, "data_missing": ["growth_prev"]}
    t.update(kw)
    return t


def check_engine():
    e = ScoreEngine(MACRO)
    high, _ = e.calculate_acceleration(ticker("A"), [])
    low, _  = e.calculate_acceleration(ticker("A", gross_margin=0.40), [])
    check("no high-margin bonus when acceleration is unmeasured (old code: x1.08)", abs(high - low) < 1e-9, (high, low))
    color, status = e.determine_color(70.0, None, False, [])
    check("a score above 65 with unmeasured acceleration is Orange, not Red (old code: Red)", color == "Orange", (color, status))
    color, _ = e.determine_color(70.0, 0.10, False, [])
    check("measured acceleration above 0.05 can still be Red", color == "Red", color)


def check_layer_guard():
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        real = render.SCORES_HISTORY_FILE
        render.SCORES_HISTORY_FILE = "scores_history.json"
        try:
            json.dump([], open("scores_history.json", "w"))
            layers = list(SUB_LAYERS)
            md = {"sub_layers": {lid: [ticker(lid[:4].upper())] for lid in layers},
                  "meta": {"generic_feed_failures": [], "session": "2026-10-06",
                           "sessions": ["2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06"]}}
            md["sub_layers"]["cooling"] = [ticker("MEAS", growth_prev=0.30, data_missing=[])]
            with patch("main._confirmed_color", return_value=("Red", "forced", "instant")):
                scored = main.stage_score(md, MACRO)
        finally:
            render.SCORES_HISTORY_FILE = real
            os.chdir(cwd)
    colors = {lid: r["best"]["color"] for lid, r in scored.items()}
    unmeasured = [lid for lid in layers if lid != "cooling"]
    check("no sub-layer reaches Red with acceleration unmeasured for all its companies (old code: Red)",
          all(colors[l] == "Orange" for l in unmeasured), colors)
    check("a sub-layer with a measured company can still be Red", colors["cooling"] == "Red", colors)


def check_labels():
    """Step 6: the page says what the number is. The layer card's
    "Momentum" was revenue acceleration (now "Rev. acceleration"), the
    expanded card gives the pp change, and a missing delta reads "not measured"."""
    scored = {"optical": {"best": {"ticker": "LITE", "score": 60.0, "color": "Orange", "fund_delta": None, "news_velocity": 1.0},
                          "all_tickers": [{"ticker": "LITE", "score": 60.0, "color": "Orange", "fund_delta": None},
                                          {"ticker": "COHR", "score": 50.0, "color": "Orange", "fund_delta": 0.132}],
                          "tickers_scored": 2, "tickers_total": 2}}
    l = json.loads(render._chain_js_data(scored, {"sub_layers": {}}, {}))[0]
    check("unmeasured acceleration reads 'not measured' on the layer card (old: 'unknown')", l["momentum_label"] == "not measured", l["momentum_label"])
    pp = {t["sym"]: t["accel_pp"] for t in l["tickers"]}
    check("the card data carries the YoY change in pp, None when unmeasured", pp == {"LITE": None, "COHR": 13.2}, pp)
    src = open(os.path.join(REPO, "render.py"), encoding="utf-8").read()
    check("the layer card says 'Rev. acceleration', not 'Momentum'",
          "Rev. acceleration ${{l.momentum_label}}" in src and "· Momentum ${{l.momentum_label}}" not in src)
    check("the expanded card shows '— not measured' or the pp change",
          '"— not measured"' in src and '" pp YoY vs prior qtr · "' in src)


def run():
    logging.disable(logging.CRITICAL)
    check_engine()
    check_layer_guard()
    check_labels()
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())

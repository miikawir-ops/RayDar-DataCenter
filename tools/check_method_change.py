"""Checks for the model-version change (PLAN.md ledger R88 step 7): scores
from model_version 3 on aren't comparable with earlier ones. Old-version
history entries are kept as published, never compared: colour
confirmation skips them, the page shows no score delta or colour-change
badge across the change ("no comparison: method changed"), the heat trail
marks the last old-version day, and a dated note says colour changes
reflect the fix, not a market move. The first new-version entry carries
methodology_change. The parent's rules. Offline; files go to a temp folder.

Run: python tools/check_method_change.py   (exit 0 when every check passes)
"""
import os
import re
import sys
import json
import logging
import datetime
import tempfile

import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from config import SUB_LAYERS, MODEL_VERSION  # noqa: E402
import main    # noqa: E402
import render  # noqa: E402

results = []
D = datetime.date.fromisoformat
SESSIONS = [d.date() for d in pd.bdate_range("2026-09-28", "2026-10-06")]
MACRO = {"vix": 18.0, "yield_10y_change": -5.0, "nasdaq_vs_spx_20d": 0.01, "data_missing": []}


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def old_entry(date, score=70.0, color="Red", version=2):
    e = {"date": date, "time": "18:00", "scores": {lid: {"score": score, "color": color} for lid in SUB_LAYERS}}
    if version is not None:
        e["model_version"] = version
    return e


def ticker(sym):
    return {"ticker": sym, "name": sym, "price": 100.0, "growth_curr": 0.30, "growth_prev": 0.25, "gm_delta": 0.01,
            "gross_margin": 0.40, "news_velocity": 4.0, "capex_div": 0.30, "vol_spike": 1.1, "price_act": 0.01,
            "analyst_upgrades": 0, "short_int_change": 0.0, "price_30d_return": 0.05, "price_momentum": 1.5,
            "peer_outperformance": 0.0, "market_cap": 1e11, "data_missing": [],
            "price_history": [100.0 + i for i in range(30)],
            "price_history_dates": [d.date().isoformat() for d in pd.bdate_range(end="2026-10-06", periods=30)],
            "data_date": "2026-10-06"}


def check_confirmation_window():
    hist = [old_entry("2026-10-01"), old_entry("2026-10-02", version=None), old_entry("2026-10-05")]
    stored, missing = main._confirmation_window("cooling", hist, SESSIONS, D("2026-10-06"))
    check("confirmation skips history scored under an older model version (old code: 3 stored)", stored == [], stored)
    check("...and doesn't report those sessions as missing", missing == [], missing)


def check_page():
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        real = render.SCORES_HISTORY_FILE
        render.SCORES_HISTORY_FILE = "scores_history.json"
        try:
            json.dump([old_entry("2026-10-01"), old_entry("2026-10-02"), old_entry("2026-10-05"),
                       old_entry("2026-10-06", score=10.0, color="Blue")], open("scores_history.json", "w"))
            md = {"sub_layers": {lid: [ticker(lid[:4].upper())] for lid in SUB_LAYERS},
                  "meta": {"generic_feed_failures": [], "session": "2026-10-06",
                           "sessions": [s.isoformat() for s in SESSIONS]}}
            scored = main.stage_score(md, MACRO)
            render.generate_dashboard(scored, MACRO, md, None)
            hist1 = json.load(open("scores_history.json"))
            html = open("index.html", encoding="utf-8").read()
            md["meta"].update(session="2026-10-07", sessions=[s.isoformat() for s in SESSIONS] + ["2026-10-07"])
            scored = main.stage_score(md, MACRO)
            render.generate_dashboard(scored, MACRO, md, None)
            hist2 = json.load(open("scores_history.json"))
        finally:
            render.SCORES_HISTORY_FILE = real
            os.chdir(cwd)
    oct6 = next(e for e in hist1 if e["date"] == "2026-10-06")
    check("an old-version entry for the same session is kept as published (old code: overwritten)",
          oct6.get("model_version") == 2 and oct6["scores"]["cooling"]["color"] == "Blue", oct6)
    first = next(e for e in hist2 if e["date"] == "2026-10-07")
    check("the first new-version entry carries methodology_change",
          first.get("model_version") == MODEL_VERSION and first.get("methodology_change") is True, sorted(first))
    check("no comparison across the change: METHOD_BREAK set, no previous session label",
          "const METHOD_BREAK = true;" in html and 'const PREV_LABEL   = "";' in html and "const HAS_YESTERDAY= false;" in html)
    check("the card says 'no comparison: method changed' rather than 'first run'", "no comparison: method changed" in html)
    note = re.search(r"<strong>Methodology change after the (\w{3} \w{3} \d+) close:</strong> ([^<]+)", html)
    check("a dated note says colour changes reflect the fix, not a market move",
          note is not None and note.group(1) == "Tue Oct 6" and "reflect the fix, not a market move" in note.group(2),
          note.groups() if note else None)
    hjs = json.loads(re.search(r"const HISTORY\s*= (\{.*?\});\n", html).group(1))
    marked = [d["date"] for d in hjs["days"] if d.get("method_boundary")]
    check("the heat trail marks the last old-version day", marked == ["2026-10-06"], marked)


def run():
    logging.disable(logging.CRITICAL)
    check_confirmation_window()
    check_page()
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())

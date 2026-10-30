"""tools/replay.py — the before/after replay (ledger R88 step 10): score and
render a saved fetch (tools/save_fetch.py) with the code in the current
directory, in a temp folder with a copy of a scores_history.json (the repo's
files are never touched). Writes a JSON snapshot (sub-layer scores, colours
and notes; company scores, colours, deltas; card ratings, bands and
forecasts) and the rendered page.

--history-as-current relabels every history entry with this code's
MODEL_VERSION, so colour confirmation runs as it would without a method
change: it separates the scoring changes from the method-change effect.

Usage (repo root):
    python tools/replay.py <fetch.json> <scores_history.json> <snap_out.json> <page_out.html> [--history-as-current]
"""
import os
import re
import sys
import json
import logging
import tempfile

repo = os.getcwd()
sys.path.insert(0, repo)
logging.disable(logging.CRITICAL)
import main    # noqa: E402
import render  # noqa: E402
from config import MODEL_VERSION  # noqa: E402

fetch_path, hist_path, snap_path, page_path = (os.path.abspath(p) for p in sys.argv[1:5])
as_current = "--history-as-current" in sys.argv[5:]
d = json.load(open(fetch_path))
hist = json.load(open(hist_path))
if as_current:
    for e in hist:
        e["model_version"] = MODEL_VERSION
with tempfile.TemporaryDirectory() as tmp:
    os.chdir(tmp)
    real = render.SCORES_HISTORY_FILE
    render.SCORES_HISTORY_FILE = "scores_history.json"
    try:
        json.dump(hist, open("scores_history.json", "w"))
        scored = main.stage_score(d["market"], d["macro"])
        render.generate_dashboard(scored, d["macro"], d["market"], d["capex"])
        page = open("index.html", encoding="utf-8").read()
    finally:
        render.SCORES_HISTORY_FILE = real
        os.chdir(repo)
open(page_path, "w", encoding="utf-8").write(page)
layers = json.loads(re.search(r"const LAYERS\s*=\s*(\[.*?\]);\n", page, re.S).group(1))
snap = {"model_version": MODEL_VERSION, "history_as_current": as_current, "layers": {}}
for lid, r in scored.items():
    l = next(x for x in layers if x["id"] == lid)
    b = r.get("best") or {}
    snap["layers"][lid] = {
        "score": b.get("score"), "color": b.get("color"), "status": b.get("status"), "note": l.get("note"),
        "news_vel": l.get("news_vel"), "momentum": l.get("momentum_label"),
        "companies": {t["ticker"]: {"score": t.get("score"), "color": t.get("color"), "delta": t.get("fund_delta"),
                                    "news": t.get("news_velocity")} for t in r.get("all_tickers", [])},
        "cards": {t["sym"]: {"rating": t["rating"], "band": t["delta_band"], "forecast": t["forecast"]["label"],
                             # The A-D rule with fund_delta in pp, as its thresholds assume (the parent's
                             # call): a proposal column, not what this code renders.
                             "rating_pp": render.company_rating(
                                 (next(x for x in r["all_tickers"] if x["ticker"] == t["sym"]).get("fund_delta") or 0) * 100
                                 if next(x for x in r["all_tickers"] if x["ticker"] == t["sym"]).get("fund_delta") is not None else None,
                                 t["color"], t["hype"])}
                  for t in l["tickers"]},
    }
open(snap_path, "w").write(json.dumps(snap, indent=1, sort_keys=True))
print(f"replayed {sum(len(x['companies']) for x in snap['layers'].values())} companies -> {snap_path}")

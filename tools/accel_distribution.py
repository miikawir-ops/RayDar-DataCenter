"""tools/accel_distribution.py — historical distribution of true YoY revenue
acceleration (change in YoY growth between consecutive quarters) for this
project's companies, from SEC EDGAR quarters cross-checked with yfinance.
Used to calibrate the thresholds that read fund_delta (instant Red, the
leader boost, Red's minimum delta, Blue's "decelerating", the A rating, the
+/-5 pp bands) against real data (ledger R88 step 9). Ported from the parent.

A firing whose previous-quarter YoY was at or below 0 is counted as a
possible trough rebound: a proxy, not a cycle analysis.

Needs SEC_USER_AGENT ("Name email"). Usage (repo root):
    python tools/accel_distribution.py [since=2021-07-01]
"""
import os
import sys
import datetime
import logging

sys.path.insert(0, os.getcwd())
logging.disable(logging.CRITICAL)

import yfinance as yf
import edgar
from config import SUB_LAYERS

since = datetime.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else datetime.date(2021, 7, 1)

rows, skipped = [], []
for layer, cfg in SUB_LAYERS.items():
    for tk in cfg["tickers"]:
        yr = yf.Ticker(tk).quarterly_financials.loc["Total Revenue"]
        yq = {k.date(): float(v) for k, v in yr.items() if v == v}
        s, note = edgar.quarterly_revenue(tk, yq)
        if not s:
            skipped.append(f"{tk} ({note})")
            continue
        ends = sorted(s)

        def yoy(e):
            p = next((x for x in ends if 350 <= (e - x).days <= 380), None)
            return s[e] / s[p] - 1 if p and s[p] else None

        ser = [(e, yoy(e)) for e in ends if e >= since]
        ser = [(e, g) for e, g in ser if g is not None]
        rows += [(tk, e2, g2 - g1, g1, g2) for (e1, g1), (e2, g2) in zip(ser, ser[1:]) if 75 <= (e2 - e1).days <= 105]

vals = sorted(r[2] for r in rows)
pct = lambda p: vals[int(p * (len(vals) - 1))] * 100
n = len(rows)
print(f"{n} company-quarters since {since}, {len({r[0] for r in rows})} companies" + (f"; skipped: {skipped}" if skipped else ""))
print("percentiles (pp): " + "  ".join(f"p{int(p*100)} {pct(p):+.1f}" for p in (.05, .1, .25, .5, .75, .9, .95, .99)))
print("per company: " + ", ".join(f"{t} {sum(1 for r in rows if r[0] == t)}" for t in sorted({r[0] for r in rows})))


def report(label, sel):
    trough = [r for r in sel if r[3] <= 0]
    print(f"{label}: {len(sel)} ({len(sel)/n:.1%}); previous YoY <= 0 (possible trough rebound): {len(trough)}")
    return sel


for label, cut in (("> +60 pp (instant Red, removed in R90)", 0.60), ("> +40 pp (leader boost floor 45)", 0.40),
                   ("> +20 pp (A rating, once in pp)", 0.20), ("> +5 pp (accelerating band; Red needs >= +5)", 0.05)):
    sel = report(label, [r for r in rows if r[2] > cut])
    if cut >= 0.40:
        for r in sorted(sel, key=lambda r: -r[2]):
            print(f"    {r[0]:5s} {r[1]}  delta {r[2]*100:+6.1f} pp  YoY {r[3]*100:+6.1f}% -> {r[4]*100:+6.1f}%")
report("< 0 (Blue today: any drop)", [r for r in rows if r[2] < 0])
report("< -5 pp (the parent's Blue threshold)", [r for r in rows if r[2] < -0.05])
print(f"between -5 and 0 pp (Blue today, not under the parent's rule): {sum(1 for r in rows if -0.05 <= r[2] < 0)} "
      f"({sum(1 for r in rows if -0.05 <= r[2] < 0)/n:.1%})")

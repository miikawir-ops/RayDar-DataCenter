"""Checks for the hyperscaler capex overlay (PLAN.md ledger R98): capex.py,
shared unchanged with the parent, replaces the average of per-company YoY
that mixed quarters. On 2026-11-01 Yahoo's newest AMZN quarter was
2026-03-31 while the others had 2026-09-30, and the old overlay averaged
them into "+93.6% avg YoY, accelerating" (accelerating meaning a level
above 30%). Now: dollars summed vs the same quarters a year earlier, EDGAR
filling the quarters Yahoo lacks, stale or missing companies named, at
least 3 of 4, direction = change in aggregate YoY (±5 pp). Offline: the
quarters are the real ones of 2026-11-01, stubbed in.

Run: python tools/check_capex.py   (exit 0 when every check passes)
"""
import os
import sys
import json
import datetime
import logging
from unittest.mock import patch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import capex   # noqa: E402
import main    # noqa: E402
import render  # noqa: E402

results = []
D = datetime.date.fromisoformat
REAL = {   # $bn, EDGAR-derived, 2026-11-01
    "MSFT":  {"2025-06-30": 17.08, "2025-09-30": 19.394, "2025-12-31": 29.876, "2026-03-31": 30.876, "2026-06-30": 35.802, "2026-09-30": 39.367},
    "GOOGL": {"2025-06-30": 22.45, "2025-09-30": 23.953, "2025-12-31": 27.851, "2026-03-31": 35.674, "2026-06-30": 44.924, "2026-09-30": 51.355},
    "AMZN":  {"2025-06-30": 32.183, "2025-09-30": 35.095, "2025-12-31": 39.522, "2026-03-31": 44.203, "2026-06-30": 54.21, "2026-09-30": 77.26},
    "META":  {"2025-06-30": 16.54, "2025-09-30": 18.829, "2025-12-31": 21.383, "2026-03-31": 18.997, "2026-06-30": 30.116, "2026-09-30": 33.942},
}


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def quarters(drop_amzn_after=None):
    q = {t: {D(k): v * 1e9 for k, v in s.items()} for t, s in REAL.items()}
    if drop_amzn_after:
        q["AMZN"] = {k: v for k, v in q["AMZN"].items() if k <= D(drop_amzn_after)}
    return q


OCF_Q3 = {"MSFT": 58.0, "GOOGL": 42.3, "AMZN": 42.4, "META": 32.8}   # $bn, quarter ending 2026-09-30


def stage_with(q):
    """main.stage_capex() with these quarters (and Q3 operating cash flow), no network."""
    def company(t):
        capex.YAHOO_TABLES[t] = "row"
        return q[t], "stub"
    with patch("capex.company_quarters", side_effect=company), \
         patch("capex.company_ocf", side_effect=lambda t: ({D("2026-09-30"): OCF_Q3[t] * 1e9}, "stub")):
        return main.stage_capex()


def check_aggregate():
    r = stage_with(quarters())
    check("stage_capex gives the shared aggregate: $201.9bn vs $97.3bn, +107.6% (old code: '+93.6% avg YoY')",
          r.get("available") and r["quarter"] == "2026-09-30" and r["included"] == 4
          and abs(r["total"] / 1e9 - 201.924) < 0.01 and abs(r["yoy"] - 1.0759) < 0.0005, {k: r.get(k) for k in ("quarter", "yoy", "included")})
    check("direction is the change in aggregate YoY: +20.6 pp -> accelerating (old code: a level above 30%)",
          r["direction"] == "accelerating" and r["change_pp"] == 20.6, (r.get("direction"), r.get("change_pp")))
    check("the site's sub-layer beneficiary map comes along", set(r["beneficiary_map"]) == {"gpu_clusters", "interconnect", "facilities"})
    tr = {c["ticker"]: c.get("trend") for c in r["companies"]}
    check("each company's own trend and breadth (R99): 2 of 4 accelerating",
          r["accelerating_companies"] == 2 and tr == {"MSFT": "decelerating", "GOOGL": "accelerating", "AMZN": "accelerating", "META": "stable"}, tr)
    f = r["funding"]
    check("funding (R99): capex 115% of operating cash flow this quarter, free cash flow −$26.4bn",
          f["available"] and abs(f["capex_to_ocf"] - 1.1506) < 0.001 and abs(f["fcf"] / 1e9 + 26.4) < 0.05, f)
    json.loads(render._capex_js_data(r))   # serialisable, no NaN


def check_stale_and_minimum():
    r = stage_with(quarters(drop_amzn_after="2026-03-31"))
    amzn = next(c for c in r["companies"] if c["ticker"] == "AMZN")
    check("a stale AMZN is named and left out, not mixed into the Q3 sum (old code: averaged in)",
          r["included"] == 3 and amzn["status"] == "stale" and amzn["latest_quarter"] == "2026-03-31", amzn)
    q = quarters(); q["AMZN"] = {}; q["META"] = {}
    r = stage_with(q)
    check("fewer than 3 companies: not available (old code: 2 of 4 was enough)", r["available"] is False and "minimum 3" in r["reason"], r.get("reason"))


def check_page_text():
    src = open(os.path.join(REPO, "render.py"), encoding="utf-8").read()
    check("the strip says 'last reported quarters', not 'avg YoY'",
          "HYPERSCALER CAPEX (LAST REPORTED QUARTERS)" in src and "avg YoY" not in src)
    check("the strip gives the dollar total, the quarter-end and each company's quarter, stale ones marked",
          "bn in the quarter ending" in src and "not included" in src and "latest quarter " in src)
    check("the strip shows breadth, the funding lines and each company's trend and capex/OCF (R99)",
          "companies accelerating" in src and "Funding: capex was" in src and "Last four quarters: capex" in src and "% of OCF" in src)
    check("the caveat says backward-looking, no guidance, cash capex as filed",
          "Company guidance isn't included" in src and "for example by including finance leases" in src)


def run():
    logging.disable(logging.CRITICAL)
    check_aggregate()
    check_stale_and_minimum()
    check_page_text()
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())

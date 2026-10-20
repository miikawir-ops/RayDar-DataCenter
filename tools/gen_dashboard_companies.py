"""Generate dashboard-companies.js from config.py (ledger R52/R53).

The ecosystem page lists the dashboard's companies per sub-layer and links to
that sub-layer's card on the dashboard (index.html#layer-<id>). The names come
from config.DISPLAY_NAMES and the sub-layers from config.SUB_LAYERS, so they're
never typed by hand in the page or its data file.

    python tools/gen_dashboard_companies.py           # write the file
    python tools/gen_dashboard_companies.py --check   # exit 1 if it's out of date

check_ecosystem.py runs the --check form, so a config change that isn't
regenerated fails the checks.
"""
import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from config import DISPLAY_NAMES, SUB_LAYERS  # noqa: E402

OUT = os.path.join(REPO, "dashboard-companies.js")


def render():
    missing = [t for l in SUB_LAYERS.values() for t in l["tickers"] if t not in DISPLAY_NAMES]
    if missing:
        raise SystemExit(f"config.DISPLAY_NAMES has no name for {missing}")
    data = {lid: {"name": l["name"], "anchor": f"layer-{lid}",
                  "companies": [DISPLAY_NAMES[t] for t in l["tickers"]]}
            for lid, l in SUB_LAYERS.items()}
    return ("// Generated from config.py by tools/gen_dashboard_companies.py; don't edit by hand.\n"
            "// The ecosystem page lists the dashboard's companies from it and links each\n"
            "// sub-layer to its card on the dashboard (index.html#<anchor>).\n"
            "const DASHBOARD_SUBLAYERS = " + json.dumps(data, indent=2, ensure_ascii=False) + ";\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the file is missing or out of date")
    args = ap.parse_args()
    text = render()
    if args.check:
        current = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else None
        if current != text:
            print("dashboard-companies.js is out of date with config.py: run tools/gen_dashboard_companies.py")
            return 1
        print("dashboard-companies.js matches config.py")
        return 0
    open(OUT, "w", encoding="utf-8", newline="\n").write(text)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

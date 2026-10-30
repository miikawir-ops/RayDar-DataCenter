"""tools/save_fetch.py — save one live fetch (market, macro, capex) as JSON
for tools/replay.py. Runs with the code in the current directory, in a temp
folder, so nothing in the repo is written (growth_history.json included).

Before/after a change (ledger R88 step 10): run it from a git worktree of
the old commit and from the new one, back to back on the same session, so
both sides see the same closes and nearly the same headlines.

Needs SEC_USER_AGENT for EDGAR on the new code. Usage (repo root):
    python tools/save_fetch.py <out.json>
"""
import os
import sys
import json
import shutil
import logging
import tempfile

repo = os.getcwd()
sys.path.insert(0, repo)
logging.disable(logging.CRITICAL)
out = os.path.abspath(sys.argv[1])
with tempfile.TemporaryDirectory() as tmp:
    os.chdir(tmp)
    try:
        import main
        market, macro = main.stage_fetch()
        capex = main.stage_capex()
    finally:
        os.chdir(repo)
json.dump({"market": market, "macro": macro, "capex": capex}, open(out, "w"), indent=1, default=str)
print(f"saved {sum(len(v) for v in market['sub_layers'].values())} companies, session {market['meta']['session']} -> {out}")

"""Timeouts, one retry and an always-printed summary for the Playwright checks (ledger R80).

check_ecosystem.py, check_interactions.py and check_layout_sweep.py load every page through
load() and run every suite through run_suite():

- a page load (goto plus the load state) gets LOAD_S seconds; a first timeout is retried once
  and logged as "RETRY <suite> <page>", a second fails the suite as
  "TIMEOUT <suite>: <page> load > 30 s";
- any other wait on a loaded page (locators, clicks) gets ACTION_MS, and a timeout there fails
  the suite as "TIMEOUT <suite>: <page>: <the action>";
- a suite gets SUITE_S seconds of wall clock, checked at each page load, and fails as
  "TIMEOUT <suite>: suite > 600 s" past it;
- a suite that times out or raises is recorded and the run goes on to the next suite, so each
  tool can always print its summary (summary() gives the retry and timeout counts for it).
"""
import time
from urllib.parse import urlsplit

from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout

LOAD_S = 30
ACTION_MS = 30_000
SUITE_S = 600
state = {"suite": "-", "page": "-", "started": 0.0, "retries": [], "failures": []}


class SuiteTimeout(Exception):
    pass


def page_name(url):
    parts = urlsplit(url)
    name = parts.path.rstrip("/").rsplit("/", 1)[-1] or "index.html"
    return name + ("#" + parts.fragment if parts.fragment else "")


def load(pg, url, wait="networkidle"):
    """Load url in pg within LOAD_S seconds, retrying once; returns the response."""
    suite, name = state["suite"], page_name(url)
    if time.monotonic() - state["started"] > SUITE_S:
        raise SuiteTimeout(f"TIMEOUT {suite}: suite > {SUITE_S} s")
    pg.set_default_timeout(ACTION_MS)
    state["page"] = name
    for attempt in (1, 2):
        try:
            resp = pg.goto(url, timeout=LOAD_S * 1000)
            pg.wait_for_load_state(wait, timeout=LOAD_S * 1000)
            return resp
        except PlaywrightTimeout:
            if attempt == 2:
                raise SuiteTimeout(f"TIMEOUT {suite}: {name} load > {LOAD_S} s")
            state["retries"].append(f"{suite} {name}")
            print(f"RETRY {suite} {name}", flush=True)
        except PlaywrightError as e:
            if attempt == 1:
                raise                                # not a timeout: no retry, the suite fails as it would have
            raise SuiteTimeout(f"TIMEOUT {suite}: {name} load > {LOAD_S} s, then the retry failed: {str(e).splitlines()[0]}")


def run_suite(name, fn, *args):
    """Run one suite; returns None when it finished, else the failure line (also printed)."""
    state.update(suite=name, page="-", started=time.monotonic())
    try:
        fn(*args)
        return None
    except SuiteTimeout as e:
        msg = str(e)
    except PlaywrightTimeout as e:
        msg = f"TIMEOUT {name}: {state['page']}: {str(e).splitlines()[0]}"
    except Exception as e:  # a crash mid-suite must still leave a summary
        msg = f"ABORT {name}: {type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}"
    state["failures"].append(msg)
    print(msg, flush=True)
    return msg


def summary():
    """One line: the retries and failed suites of this run."""
    r, f = state["retries"], state["failures"]
    return (f"retries {len(r)}" + (f" ({'; '.join(r)})" if r else "")
            + f", suites timed out or aborted {len(f)}" + (f" ({'; '.join(f)})" if f else ""))

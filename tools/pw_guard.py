"""Timeouts, one retry and an always-printed summary for the Playwright checks (ledger R80).

check_ecosystem.py, check_interactions.py and check_layout_sweep.py load every page through
load() and run every suite through run_suite():

- a page load waits for the load event (not network idle, which Playwright advises against for
  tests; R81), then for the elements the page's own script builds (READY) and the web fonts; it
  gets LOAD_S seconds; a first timeout is retried once
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


# What each page's script must have built before a suite can use it (R81), by page and, for the
# two index.html pages, by folder. Waited for as "attached", so elements hidden on phones count.
READY = {
    "ecosystem.html": ("#hotspot-operator", "#node-operator", "#wt-title"),   # poster, explorer SVG, walkthrough
    "business-models/index.html": ("#bm-header .bm-bar", "#kerrokset .lr-zone", "#lr-detail .zd-title"),
    "business-models/glossary.html": ("#bm-header .bm-bar", ".glossary-card"),
    "business-models/*": ("#bm-header .bm-bar",),
    "index.html": ("#bottleneck-strip > *", "#chain .layer"),               # the dashboard
}


def ready_for(url):
    path = urlsplit(url).path
    name = path.rstrip("/").rsplit("/", 1)[-1] or "index.html"
    if "/business-models/" in path or path.endswith("/business-models"):
        return READY.get("business-models/" + name, READY["business-models/*"] if name.endswith(".html") or name == "index.html" else ())
    return READY.get(name, ())


def settled(pg, timeout_s=LOAD_S):
    """After a load or a navigating click: the load event, the page's READY elements, the fonts."""
    pg.wait_for_load_state("load", timeout=timeout_s * 1000)
    for sel in ready_for(pg.url):
        pg.wait_for_selector(sel, state="attached", timeout=timeout_s * 1000)
    pg.evaluate("document.fonts.ready.then(() => true)")


def click_to(pg, locator):
    """Click a link that opens another page: wait for that navigation, then settled()."""
    with pg.expect_navigation(wait_until="load", timeout=LOAD_S * 1000):
        locator.click()
    settled(pg)


def load(pg, url):
    """Load url in pg within LOAD_S seconds, retrying once; returns the response."""
    suite, name = state["suite"], page_name(url)
    if time.monotonic() - state["started"] > SUITE_S:
        raise SuiteTimeout(f"TIMEOUT {suite}: suite > {SUITE_S} s")
    pg.set_default_timeout(ACTION_MS)
    state["page"] = name
    for attempt in (1, 2):
        try:
            resp = pg.goto(url, wait_until="load", timeout=LOAD_S * 1000)
            if resp is None or resp.ok:              # an error page has no app elements to wait for
                settled(pg)
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

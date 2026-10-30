"""Link check (ledger R92): every internal and external link on the public pages, after deploy.

Collects, from each page rendered in Chromium: every <a href>, plus the page's own resources (stylesheets,
scripts, images, icons, og:image). It also reads the URLs out of every script the pages load from the
site (the ecosystem data file, dashboard-companies.js, business-models/assets/*.js): source links that
only reach the DOM when a card opens. Each URL is then fetched with a full browser User-Agent (a short one drew 403s from
some sites in AI_valuechain's check), without following redirects, and reported as:

  ok        200
  redirect  3xx, with where it ends up and that final status
  bot?      401/403/429/503, or a challenge page: likely bot protection, open it in a browser to confirm
  BROKEN    anything else (404, 5xx, DNS or TLS error, timeout)

Internal links (on the base's own host) that are broken fail the run; external ones are only listed.
Run against live after a deploy:

    python tools/check_links.py --base https://datacenter.raydar.fi/
"""
import argparse
import re
import sys
import urllib.error
import urllib.request
from urllib.parse import urldefrag, urljoin, urlsplit

from playwright.sync_api import sync_playwright

import pw_guard

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0.0.0 Safari/537.36")
PAGES = ("", "ecosystem.html", "business-models/", "business-models/public-cloud.html",
         "business-models/gpu-cloud.html", "business-models/retail-colocation.html",
         "business-models/wholesale-colocation.html", "business-models/own-data-center.html",
         "business-models/glossary.html", "business-models/financing.html",
         "business-models/specialised-models.html", "business-models/value-chain.html",
         "business-models/why-finland.html")
NOT_LINKS = ("http://www.w3.org/",)            # XML namespaces in scripts, never fetched by a browser
COLLECT = """() => [
  ...[...document.querySelectorAll('a[href]')].map(a => a.href),
  ...[...document.querySelectorAll('link[href]')].map(l => l.href),
  ...[...document.querySelectorAll('script[src], img[src]')].map(e => e.src),
  ...[...document.querySelectorAll('meta[property="og:image"], meta[property="og:url"]')].map(m => m.content),
]"""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OPENER = urllib.request.build_opener(NoRedirect)
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
           "Accept-Language": "en-US,en;q=0.9,fi;q=0.8"}


def get(url, follow, limit=4096):
    """(status, location, body head) for one GET; status is an error string when there is no response."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with (urllib.request.urlopen if follow else OPENER.open)(req, timeout=30) as r:
            return r.status, r.headers.get("Location"), r.read(limit)
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location"), e.read(limit) if e.fp else b""
    except Exception as e:                      # DNS, TLS, timeout
        return f"{type(e).__name__}: {e}"[:120], None, b""


def classify(url):
    status, loc, body = get(url, follow=False)
    if isinstance(status, str):                 # no response: retry once (a TLS error on fingrid.fi was transient)
        status, loc, body = get(url, follow=False)
    if status in (301, 302, 303, 307, 308):
        final, _, fbody = get(urljoin(url, loc or ""), follow=True)
        kind = "redirect" if final == 200 else "bot?" if final in (401, 403, 429, 503) else "BROKEN"
        return kind, f"{status} -> {loc} ({final})"
    if status == 200:
        return "ok", "200"
    challenge = re.search(rb"captcha|cf-chl|challenge-platform|Just a moment\.\.\.", body, re.I)
    if status in (401, 403, 429, 503) or (isinstance(status, int) and status < 500 and challenge):
        return "bot?", str(status)
    return "BROKEN", str(status)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="https://datacenter.raydar.fi/")
    args = ap.parse_args()
    base = args.base if args.base.endswith("/") else args.base + "/"
    host = urlsplit(base).netloc
    found = {}                                  # url -> first page it was seen on

    def collect(b):
        pg = b.new_page(viewport={"width": 1680, "height": 1000})
        for path in PAGES:
            pw_guard.load(pg, base + path)
            for u in pg.evaluate(COLLECT):
                found.setdefault(urldefrag(u)[0], path or "dashboard")

    pw_guard.keep_awake()
    with sync_playwright() as p:
        b = p.chromium.launch()
        failed = pw_guard.run_suite("collect", collect, b)
        b.close()
    if failed:
        return 1
    scripts = [u[len(base):] for u in found if u.startswith(base) and u.endswith(".js")]
    for s in scripts:
        _, _, body = get(base + s, follow=True, limit=-1)
        for u in re.findall(rb"https?://[^\"'\s)<>\\]+", body):
            u = u.decode()
            if not u.startswith(NOT_LINKS):
                found.setdefault(urldefrag(u)[0], s)
    urls = sorted(u for u in found if u.startswith(("http://", "https://")))
    rows = {"ok": [], "redirect": [], "bot?": [], "BROKEN": []}
    for u in urls:
        kind, detail = classify(u)
        rows[kind].append((u, detail, found[u]))
    internal_broken = [r for r in rows["BROKEN"] if urlsplit(r[0]).netloc == host]
    print(f"{len(urls)} unique URLs: {len(rows['ok'])} ok, {len(rows['redirect'])} redirect, "
          f"{len(rows['bot?'])} bot?, {len(rows['BROKEN'])} broken ({len(internal_broken)} internal)")
    for kind in ("BROKEN", "bot?", "redirect"):
        if rows[kind]:
            print(f"\n== {kind}")
            for u, detail, where in rows[kind]:
                side = "internal" if urlsplit(u).netloc == host else "external"
                print(f"  {detail:<14.200} {side}  {u}   (on {where})")
    return 1 if internal_broken else 0


if __name__ == "__main__":
    sys.exit(main())

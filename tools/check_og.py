"""Link-preview check (ledger R92): every public page carries the og/twitter tags, with absolute URLs,
and its og:image and favicons load.

Per page:
  - description, og:title, og:description, og:type=website, og:url, og:image, og:image:width=1200,
    og:image:height=627, og:image:alt, og:locale (en_US or fi_FI as the page's language),
    twitter:card=summary_large_image, all present and non-empty;
  - og:url is the page's own https://datacenter.raydar.fi/ URL, og:image an absolute URL on that site;
  - og:image returns 200 with image/png or image/jpeg and is exactly 1200x627;
  - the favicon.svg, favicon.png and apple-touch-icon.png links resolve with 200.

Against a local server (the default base) the absolute site URLs are fetched from the base instead, so
the files about to be deployed are the ones checked. Against live:

    python tools/check_og.py --base https://datacenter.raydar.fi/
"""
import argparse
import struct
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin

SITE = "https://datacenter.raydar.fi/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0.0.0 Safari/537.36")
# Public pages: path under the site (as og:url names it) and the page's locale.
PAGES = {
    "": "en_US",
    "ecosystem.html": "en_US",
    "business-models/": "fi_FI",
    "business-models/public-cloud.html": "fi_FI",
    "business-models/gpu-cloud.html": "fi_FI",
    "business-models/retail-colocation.html": "fi_FI",
    "business-models/wholesale-colocation.html": "fi_FI",
    "business-models/own-data-center.html": "fi_FI",
    "business-models/glossary.html": "fi_FI",
    "business-models/financing.html": "fi_FI",
    "business-models/specialised-models.html": "fi_FI",
    "business-models/value-chain.html": "fi_FI",
    "business-models/why-finland.html": "fi_FI",
}
REQUIRED = ("description", "og:title", "og:description", "og:type", "og:url", "og:image", "og:image:width",
            "og:image:height", "og:image:alt", "og:locale", "twitter:card")
ICONS = (("icon", "favicon.svg"), ("icon", "favicon.png"), ("apple-touch-icon", "apple-touch-icon.png"))

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'ok  ' if ok else 'FAIL'} {name}" + ("" if ok else f"  [{detail}]"))


class Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta, self.links = {}, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and (a.get("property") or a.get("name")):
            self.meta.setdefault(a.get("property") or a.get("name"), a.get("content") or "")
        elif tag == "link" and a.get("rel") and a.get("href"):
            self.links.append((a["rel"], a["href"]))


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), b""


def image_size(data):
    """(width, height) of a PNG or JPEG, or None."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                return None
            marker, seg = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + seg
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://127.0.0.1:8765/")
    args = ap.parse_args()
    base = args.base if args.base.endswith("/") else args.base + "/"
    on_base = lambda url: base + url[len(SITE):] if url.startswith(SITE) else url
    images = {}
    for path, locale in PAGES.items():
        tag = path or "dashboard"
        status, _, body = fetch(base + path)
        check(f"{tag}: page 200", status == 200, status)
        if status != 200:
            continue
        head = Head()
        head.feed(body.decode("utf-8", "replace"))
        m = head.meta
        missing = [k for k in REQUIRED if not m.get(k, "").strip()]
        check(f"{tag}: all tags present", not missing, missing)
        check(f"{tag}: og:type website", m.get("og:type") == "website", m.get("og:type"))
        check(f"{tag}: twitter:card summary_large_image", m.get("twitter:card") == "summary_large_image", m.get("twitter:card"))
        check(f"{tag}: og:locale {locale}", m.get("og:locale") == locale, m.get("og:locale"))
        check(f"{tag}: og:url is its own absolute URL", m.get("og:url") == SITE + path, m.get("og:url"))
        img = m.get("og:image", "")
        check(f"{tag}: og:image absolute on the site", img.startswith(SITE), img)
        check(f"{tag}: og:image size tags 1200x627",
              (m.get("og:image:width"), m.get("og:image:height")) == ("1200", "627"),
              (m.get("og:image:width"), m.get("og:image:height")))
        if img.startswith(SITE):
            if img not in images:
                s, ctype, data = fetch(on_base(img))
                images[img] = (s, ctype.split(";")[0].strip(), image_size(data))
            s, ctype, size = images[img]
            check(f"{tag}: og:image 200", s == 200, f"{s} {img}")
            check(f"{tag}: og:image png/jpeg", ctype in ("image/png", "image/jpeg"), ctype)
            check(f"{tag}: og:image is 1200x627", size == (1200, 627), size)
        for rel, name in ICONS:
            href = next((h for r, h in head.links if r == rel and h.endswith(name)), None)
            ok = href is not None and fetch(urljoin(base + path, href))[0] == 200
            check(f"{tag}: {name} linked and 200", ok, href)
    fails = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
    return 1 if fails or not results else 0


if __name__ == "__main__":
    sys.exit(main())

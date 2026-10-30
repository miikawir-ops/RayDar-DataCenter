"""Build the two link-preview images (ledger R92), 1200x627 JPEG, from the site's existing art:

  og-image.jpg                            the ecosystem poster, for the dashboard and ecosystem.html
  business-models/assets/og-image-fi.jpg  the layered data-center image, for the business-models pages

Each is a crop of the art with the page title set in the site's own fonts (the dashboard and the
ecosystem page use the system stack; the explainer its self-hosted Space Grotesk and IBM Plex Sans).
No live data: no scores, colours or company names. Rendered in Chromium (Playwright), so the fonts
are the real ones. Re-run after changing the art or the titles:

    python tools/make_og_images.py
"""
import os
import pathlib

from playwright.sync_api import sync_playwright

REPO = pathlib.Path(__file__).resolve().parent.parent
W, H = 1200, 627

# Text on the images (Ray approves, ledger R92).
POSTER_TITLE = "RayDar Data Center"
POSTER_SUB = "Data center ecosystem · Daily bottleneck signals"
LAYERS_TITLE = "Datakeskusten liiketoimintamallit"
LAYERS_SUB = "RayDar Data Center"

POSTER = """<!doctype html><meta charset="utf-8"><style>
html,body{margin:0;width:1200px;height:627px;overflow:hidden;background:#0E1628}
.art{position:absolute;inset:0;background:url('%(art)s') no-repeat;background-size:1536px auto;background-position:0 -100px}
.shade{position:absolute;inset:0;background:linear-gradient(90deg,rgba(14,22,40,.95) 0%%,rgba(14,22,40,.90) 48%%,rgba(14,22,40,0) 72%%)}
.text{position:absolute;left:56px;bottom:64px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#fff}
h1{margin:0;font-size:58px;font-weight:500;letter-spacing:-1.5px;line-height:1.05}
p{margin:14px 0 0;font-size:23px;letter-spacing:.04em;background:linear-gradient(90deg,#85B7EB,#AFA9EC);-webkit-background-clip:text;color:transparent}
</style><div class="art"></div><div class="shade"></div><div class="text"><h1>%(title)s</h1><p>%(sub)s</p></div>"""

LAYERS = """<!doctype html><meta charset="utf-8"><style>
@font-face{font-family:'Space Grotesk';font-weight:300 700;src:url('%(fonts)s/space-grotesk-var-latin.woff2') format('woff2')}
@font-face{font-family:'IBM Plex Sans';font-weight:100 700;src:url('%(fonts)s/ibm-plex-sans-var-latin.woff2') format('woff2')}
html,body{margin:0;width:1200px;height:627px;overflow:hidden;background:#12222E}
.art{position:absolute;inset:0;background:url('%(art)s') no-repeat;background-size:1200px auto;background-position:0 -8px}
.shade{position:absolute;inset:0;background:linear-gradient(0deg,rgba(18,34,46,.92) 0%%,rgba(18,34,46,.72) 24%%,rgba(18,34,46,0) 46%%)}
.text{position:absolute;left:52px;bottom:44px;color:#fff}
h1{margin:0;font-family:'Space Grotesk',sans-serif;font-size:56px;font-weight:700;letter-spacing:-.5px;line-height:1.05}
p{margin:10px 0 0;font-family:'IBM Plex Sans',sans-serif;font-size:22px;font-weight:500;color:#F0A46E;letter-spacing:.03em}
</style><div class="art"></div><div class="shade"></div><div class="text"><h1>%(title)s</h1><p>%(sub)s</p></div>"""


def render(pg, html, out):
    tmp = REPO / "Output" / "og_build.html"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text(html, encoding="utf-8")
    pg.goto(tmp.as_uri(), wait_until="load")
    pg.evaluate("document.fonts.ready.then(() => true)")
    pg.screenshot(path=str(out), type="jpeg", quality=88, clip={"x": 0, "y": 0, "width": W, "height": H})
    print(f"{out.relative_to(REPO)}: {os.path.getsize(out) // 1024} KB")


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        render(pg, POSTER % {"art": (REPO / "assets" / "ecosystem-v2.webp").as_uri(), "title": POSTER_TITLE, "sub": POSTER_SUB},
               REPO / "og-image.jpg")
        render(pg, LAYERS % {"art": (REPO / "business-models" / "assets" / "datakeskus-kerrokset.webp").as_uri(),
                             "fonts": (REPO / "business-models" / "assets" / "fonts").as_uri(), "title": LAYERS_TITLE, "sub": LAYERS_SUB},
               REPO / "business-models" / "assets" / "og-image-fi.jpg")
        b.close()


if __name__ == "__main__":
    main()

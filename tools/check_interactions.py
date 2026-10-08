"""Interaction checks for the business-models explainer: chrome, navigation,
glossary tooltips, deep links and swipe behaviour, from 1680px down to 360px.

Three suites (all run by default):
  hub    the hub: tooltips (hover, click-pin, Esc, keyboard focus), stepper and
         deep links, matrix row alignment at 1440/1280/1024, phone swipe track
  cards  the five model cards: stepper, glossary tags, overflow, layer-cake spans
  pages  value chain, financing, specialised models, Why Finland, glossary:
         page nav (inline vs "Sivut" menu), tags, overflow, links between pages

Every run also checks for console errors and third-party requests (anything
not served from --base's origin). Touch is Chromium emulation, not a real device.

Run all three explainer checks after any explainer change (PLAN.md step 8):
    python tools/check_port_text.py --all      # text identity with the approved source
    python tools/check_layout_sweep.py         # layout at every width, 1024-1680px
    python tools/check_interactions.py         # this file

Needs Playwright (Chromium) and the site served locally, e.g. from the repo root:
    python -m http.server 8765 --bind 127.0.0.1
    python tools/check_interactions.py
    python tools/check_interactions.py --suite hub --shots Output/screenshots/business-models
    python tools/check_interactions.py --base https://miikawir-ops.github.io/RayDar-DataCenter/business-models/
The hub suite also follows the header's links to the dashboard and the ecosystem
page. Locally the dashboard root (index.html) exists only after `python main.py
--now` (it's generated and gitignored); without it that check fails.

Exit code 0 when every check passes, 1 otherwise.
"""
import argparse
import os
import sys
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

CARDS = ["public-cloud", "gpu-cloud", "retail-colocation", "wholesale-colocation", "own-data-center"]
PAGES = ["value-chain", "financing", "specialised-models", "why-finland", "glossary"]
# Widths per page type: desktop, laptop, small laptop, tablet, two phones.
WIDTHS = ((1680, 1100, False), (1280, 900, False), (1024, 900, False), (820, 1100, True), (390, 844, True), (360, 740, True))

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


class Run:
    """Where to load pages from and where (if anywhere) to save screenshots."""

    def __init__(self, base, shots):
        self.base = base if base.endswith("/") else base + "/"
        parts = urlsplit(self.base)
        self.origin = f"{parts.scheme}://{parts.netloc}/"
        self.shots = shots
        if shots:
            os.makedirs(shots, exist_ok=True)

    def shot(self, pg, name, **kw):
        if self.shots:
            pg.screenshot(path=os.path.join(self.shots, name), **kw)

    def third_party(self, urls):
        return [u for u in urls if not u.startswith(self.origin) and not u.startswith("data:")]


def page_width_overflow(pg):
    return pg.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")


# -- hub -----------------------------------------------------------------------
HUB_TIP = """() => { const t=document.getElementById('gloss-tip'); if(!t||t.hidden) return null;
  const r=t.getBoundingClientRect(); return {term:t.querySelector('.gloss-tip-term').textContent,
  left:r.left,right:r.right,top:r.top,bottom:r.bottom,vw:document.documentElement.clientWidth,vh:document.documentElement.clientHeight}}"""


def instrument(page, log):
    page.on("console", lambda m: log.append(("console", m.type, m.text)) if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: log.append(("pageerror", str(e))))
    page.on("request", lambda r: log.append(("req", r.url)))


def tip_state(page):
    return page.evaluate(HUB_TIP)


def current_step(page):
    return page.evaluate("() => { const a=document.querySelector('.bm-step[aria-current]'); return a ? a.dataset.step : null }")


def settle(page, ms=900):
    page.wait_for_timeout(ms)


def on_screen(t):
    return t and t["left"] >= 0 and t["right"] <= t["vw"] and t["top"] >= 0 and t["bottom"] <= t["vh"]


def suite_hub(b, run):
    hub = run.base + "index.html"

    # Desktop 1680
    log = []
    ctx = b.new_context(viewport={"width": 1680, "height": 1050})
    pg = ctx.new_page()
    instrument(pg, log)
    pg.goto(hub)
    pg.wait_for_load_state("networkidle")
    pg.evaluate("document.fonts.ready")
    errs = [l for l in log if l[0] in ("console", "pageerror")]
    check("desktop: no console errors/warnings or page errors", not errs, str(errs))
    reqs = [l[1] for l in log if l[0] == "req"]
    third = run.third_party(reqs)
    check("no third-party requests", not third, str(third))
    fonts = sorted({u.rsplit("/", 1)[1] for u in reqs if "/fonts/" in u})
    check("self-hosted fonts requested", len(fonts) >= 3, ", ".join(fonts))
    fam = pg.evaluate("""() => ['IBM Plex Sans','IBM Plex Mono','Space Grotesk'].map(f => [f,
        [...document.fonts].some(ff => ff.family.replace(/"/g,'')===f && ff.status==='loaded')])""")
    check("all three families loaded", all(ok for _, ok in fam), str(fam))
    g = pg.evaluate("""() => ({n:document.querySelectorAll('[data-g]').length,
        resolved:[...document.querySelectorAll('[data-g]')].every(e=>e.tabIndex===0 && BM_GLOSSARY[e.dataset.g]),
        total:Object.keys(BM_GLOSSARY).length})""")
    check("glossary: 13 tagged terms all resolve; 68 entries loaded",
          g["n"] == 13 and g["resolved"] and g["total"] == 68, f"{g['n']} tagged, {g['total']} entries")
    ow = page_width_overflow(pg)
    check("desktop 1680: no horizontal page overflow", ow <= 0, f"overflow {ow}px")
    check("desktop: no step current initially", current_step(pg) is None)
    run.shot(pg, "01_desktop_1680_full.png", full_page=True)

    pg.locator('.gloss[data-g="gpu_hour"]').hover()
    settle(pg, 300)
    t = tip_state(pg)
    check("desktop: hover shows tooltip inside viewport", t and t["term"] == "GPU-tunti" and on_screen(t), str(t))
    pg.mouse.move(5, 1000)
    settle(pg, 200)
    check("desktop: tooltip hides when pointer leaves", tip_state(pg) is None)
    # Fast click right after the pointer arrives; wait past the 80ms hover
    # delay before leaving (regression: the late hover timer un-pinned it).
    pg.locator('.gloss[data-g="operate"]').click()
    settle(pg, 200)
    pg.mouse.move(5, 1000)
    settle(pg, 200)
    t = tip_state(pg)
    check("desktop: click pins tooltip (survives the hover delay, stays after pointer leaves)", t and t["term"] == "Operoida", str(t))
    pg.keyboard.press("Escape")
    settle(pg, 100)
    check("desktop: Esc closes tooltip", tip_state(pg) is None)
    # Keyboard focus on a term below the fold: the browser scrolls it into
    # view (regression: that scroll closed the tooltip it had just opened).
    pg.evaluate("window.scrollTo(0,0)")
    pg.set_viewport_size({"width": 1680, "height": 700})
    settle(pg, 200)
    pg.locator('.gloss[data-g="reit"]').focus()
    settle(pg, 400)
    t = tip_state(pg)
    desc = pg.locator('.gloss[data-g="reit"]').get_attribute("aria-describedby")
    term_r = pg.evaluate("() => { const r=document.querySelector('.gloss[data-g=\"reit\"]').getBoundingClientRect(); return {top:r.top,bottom:r.bottom} }")
    scrolled = pg.evaluate("scrollY")
    attached = t and (abs(t["bottom"] + 8 - term_r["top"]) < 2 or abs(t["top"] - 8 - term_r["bottom"]) < 2)
    check("desktop: focusing an off-screen term scrolls it in, tooltip stays and sits next to it",
          scrolled > 0 and t and t["term"] == "REIT" and desc == "gloss-tip" and attached and on_screen(t),
          f"scrollY {scrolled}, tip {t}, term {term_r}")
    pg.keyboard.press("Tab")
    settle(pg, 150)
    t = tip_state(pg)
    check("desktop: Tab to the next term moves the tooltip to it", t and t["term"] == "Build-to-suit", str(t))
    pg.locator(".bm-family").first.focus()
    settle(pg, 150)
    check("desktop: focus leaving the terms closes it", tip_state(pg) is None)
    pg.set_viewport_size({"width": 1680, "height": 1050})
    pg.mouse.click(5, 300)
    settle(pg, 100)

    pg.locator('.bm-step[data-step="wholesale-colocation"]').click()
    settle(pg)
    st = pg.evaluate("() => ({hash:location.hash, active:[...document.querySelectorAll('.model.is-active')].map(m=>m.id)})")
    check("desktop: stepper click marks column + step + hash",
          st["active"] == ["wholesale-colocation"] and st["hash"] == "#wholesale-colocation"
          and current_step(pg) == "wholesale-colocation", str(st))
    pg.evaluate("window.scrollTo(0,0)")
    settle(pg, 200)
    pg.locator('.gloss[data-g="gpu_hour"]').hover()
    settle(pg, 300)
    run.shot(pg, "02_desktop_1680_step4_active_tooltip.png")
    ctx.close()

    ctx = b.new_context(viewport={"width": 1680, "height": 1050})
    pg = ctx.new_page()
    pg.goto(hub + "#own-data-center")
    pg.wait_for_load_state("networkidle")
    settle(pg, 400)
    st = pg.evaluate("() => [...document.querySelectorAll('.model.is-active')].map(m=>m.id)")
    check("desktop: deep link #own-data-center selects column 5 + step 5",
          st == ["own-data-center"] and current_step(pg) == "own-data-center", str(st))
    ctx.close()

    # Narrower desktops
    for w in (1440, 1280, 1024):
        ctx = b.new_context(viewport={"width": w, "height": 900})
        pg = ctx.new_page()
        pg.goto(hub)
        pg.wait_for_load_state("networkidle")
        pg.evaluate("document.fonts.ready")
        align = pg.evaluate("""() => { const cols=[document.querySelector('.matrix-labels'),...document.querySelectorAll('.model')];
            let worst=0; for(let i=0;i<11;i++){ const tops=(i<2 ? cols.slice(1) : cols).map(c=>c.children[i].getBoundingClientRect().top);
              worst=Math.max(worst, Math.max(...tops)-Math.min(...tops)); } return worst }""")
        over = pg.evaluate("() => [...document.querySelectorAll('.model > .cell')].filter(c=>c.scrollHeight>c.clientHeight+1).length")
        ow = page_width_overflow(pg)
        chain = pg.evaluate("() => [...document.querySelectorAll('.vc .scroll-x__inner')].map(i=>i.scrollWidth>i.clientWidth)")
        check(f"desktop {w}: matrix rows aligned across columns (subgrid)", align < 0.5, f"max row-top spread {align:.2f}px")
        check(f"desktop {w}: no cell content overflows its row", over == 0, f"{over} cells")
        check(f"desktop {w}: no horizontal page overflow", ow <= 0, f"{ow}px; value-chain rows scroll: {chain}")
        run.shot(pg, f"{'03' if w == 1440 else '04' if w == 1280 else '05'}_desktop_{w}_full.png", full_page=True)
        ctx.close()

    # Phones
    for w, h in ((390, 844), (360, 740)):
        log = []
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = ctx.new_page()
        instrument(pg, log)
        pg.goto(hub)
        pg.wait_for_load_state("networkidle")
        pg.evaluate("document.fonts.ready")
        errs = [l for l in log if l[0] in ("console", "pageerror")]
        check(f"phone {w}: no console errors", not errs, str(errs))
        ow = page_width_overflow(pg)
        check(f"phone {w}: no horizontal page scroll", ow <= 0, f"{ow}px")
        cur = pg.evaluate("() => document.querySelector('.bm-steps-current').textContent")
        check(f"phone {w}: step 1 current initially, name shown",
              current_step(pg) == "public-cloud" and cur == "Julkinen pilvi", cur)
        hdr = pg.evaluate("""() => [...document.querySelectorAll('.bm-bar,.bm-steps')].map(e => {
            const r=e.getBoundingClientRect(); const kids=[...e.querySelectorAll('*')].filter(k=>k.offsetParent!==null);
            return Math.max(0, ...kids.map(k=>k.getBoundingClientRect().right - r.right)) })""")
        check(f"phone {w}: header rows fit (nothing past the right edge)", max(hdr) <= 0.5, f"{hdr}")
        cw = pg.evaluate("() => { const t=document.getElementById('matrix'); return [t.querySelector('.model').getBoundingClientRect().width, t.clientWidth] }")
        check(f"phone {w}: one model per screen with peek of next", 0.75 < cw[0] / cw[1] < 0.95, f"card {cw[0]:.0f}px of {cw[1]}px")
        if w == 390:
            run.shot(pg, "06_phone_390_top.png")
            pg.evaluate("() => { const y=document.getElementById('matrix').getBoundingClientRect().top + scrollY - 60; scrollTo(0,y) }")
            settle(pg, 200)
            run.shot(pg, "07_phone_390_matrix_card1.png")

        pg.locator('.bm-step[data-step="retail-colocation"]').tap()
        settle(pg, 1200)
        pos = pg.evaluate("""() => { const t=document.getElementById('matrix'); const c=document.getElementById('retail-colocation');
            return {offset: c.getBoundingClientRect().left - t.getBoundingClientRect().left - parseFloat(getComputedStyle(t).scrollPaddingLeft),
                    hash: location.hash, cardTop: c.getBoundingClientRect().top} }""")
        check(f"phone {w}: tap step 3 -> card 3 snapped into view, hash set",
              abs(pos["offset"]) < 2 and pos["hash"] == "#retail-colocation"
              and current_step(pg) == "retail-colocation" and pos["cardTop"] >= 0, str(pos))

        pg.locator('.gloss[data-g="rack"]').tap()
        settle(pg, 200)
        t = tip_state(pg)
        check(f"phone {w}: tap term inside swipe card shows tooltip fully on screen", t and t["term"] == "Räkki" and on_screen(t), str(t))
        ow2 = page_width_overflow(pg)
        check(f"phone {w}: open tooltip causes no horizontal scroll", ow2 <= 0, f"{ow2}px")
        if w == 390:
            run.shot(pg, "08_phone_390_card3_tooltip.png")
        pg.locator('.gloss[data-g="rack"]').tap()
        settle(pg, 150)
        check(f"phone {w}: second tap on same term closes tooltip", tip_state(pg) is None)
        pg.locator('.gloss[data-g="remote_hands"]').tap()
        settle(pg, 150)
        t = tip_state(pg)
        check(f"phone {w}: term near card's right side: tooltip on screen", t and t["term"] == "Remote hands" and on_screen(t), str(t))
        pg.locator('#retail-colocation .cell--why').tap()
        settle(pg, 150)
        check(f"phone {w}: tap elsewhere closes tooltip", tip_state(pg) is None)

        pg.evaluate("""() => { const t=document.getElementById('matrix'); const c=document.getElementById('wholesale-colocation');
            t.scrollTo({left: t.scrollLeft + c.getBoundingClientRect().left - t.getBoundingClientRect().left - 16}) }""")
        settle(pg, 500)
        hs = pg.evaluate("location.hash")
        check(f"phone {w}: swiping to card 4 moves stepper + hash",
              current_step(pg) == "wholesale-colocation" and hs == "#wholesale-colocation", f"{current_step(pg)} {hs}")

        pg.evaluate("window.scrollTo(0, 1400)")
        settle(pg, 200)
        sticky = pg.evaluate("() => ({steps: document.querySelector('.bm-steps').getBoundingClientRect().top, bar: document.querySelector('.bm-bar').getBoundingClientRect().top})")
        check(f"phone {w}: stepper row stays at top when scrolled, bar row scrolls away",
              abs(sticky["steps"]) < 1 and sticky["bar"] < -30, str(sticky))

        pg.locator('.gloss[data-g="operate"]').scroll_into_view_if_needed()
        settle(pg, 200)
        pg.locator('.gloss[data-g="operate"]').tap()
        settle(pg, 200)
        t = tip_state(pg)
        check(f"phone {w}: tooltip on dark-panel term fully on screen", t and t["term"] == "Operoida" and on_screen(t), str(t))
        if w == 390:
            run.shot(pg, "09_phone_390_dark_panel_tooltip.png")
        pg.locator(".terms-note").tap()
        pg.evaluate("window.scrollTo(0,0)")
        settle(pg, 200)
        run.shot(pg, f"{'10_phone_390' if w == 390 else '11_phone_360'}_full.png", full_page=True)
        ctx.close()

        ctx = b.new_context(viewport={"width": w, "height": h}, is_mobile=True, has_touch=True)
        pg = ctx.new_page()
        pg.goto(hub + "#own-data-center")
        pg.wait_for_load_state("networkidle")
        settle(pg, 600)
        # Card 5 is the last card: the track ends before it can reach the
        # snap line, so "shown" means fully visible inside the track.
        off = pg.evaluate("""() => { const t=document.getElementById('matrix').getBoundingClientRect(); const r=document.getElementById('own-data-center').getBoundingClientRect();
            return {left: r.left - t.left, right: t.right - r.right, top: r.top, vh: innerHeight} }""")
        check(f"phone {w}: deep link #own-data-center shows card 5 fully + step 5",
              off["left"] >= 0 and off["right"] >= 0 and 0 <= off["top"] < off["vh"] and current_step(pg) == "own-data-center", str(off))
        ctx.close()

    # The header's family links (Daily signals, Ecosystem map) reach their pages.
    ctx = b.new_context()
    pg = ctx.new_page()
    pg.goto(hub)
    targets = pg.evaluate("() => [...document.querySelectorAll('.bm-header .bm-family')].map(a => a.href)")
    check("header: two family links", len(targets) == 2, str(targets))
    for url in targets:
        r = pg.goto(url)
        check(f"header family link resolves: {url.replace(run.origin, '/')}", r and r.status == 200, str(r and r.status))
    ctx.close()


# glossary.js turns a tag with no glossary entry into plain text (drops the
# .gloss class) and logs a warning, so the tag checks count every [data-g]
# element, not just those still marked .gloss.

# -- model cards ---------------------------------------------------------------
TIP = """() => { const t=document.getElementById('gloss-tip'); if(!t||t.hidden) return null; const r=t.getBoundingClientRect();
  return {term:t.querySelector('.gloss-tip-term').textContent, l:r.left, r:r.right, t:r.top, b:r.bottom,
          vw:document.documentElement.clientWidth, vh:document.documentElement.clientHeight} }"""


def tip_on_screen(t):
    return t and t["l"] >= 0 and t["r"] <= t["vw"] and t["t"] >= 0 and t["b"] <= t["vh"]


# Each spanning role cell must line up with the layers it spans (top of first, bottom of last).
CAKE = """() => { let worst = 0; const out = [];
  document.querySelectorAll('.cake').forEach(cake => {
    const layers = [...cake.querySelectorAll('.layer')].map(l => l.getBoundingClientRect());
    const roles = [...cake.querySelectorAll('.role')];
    let row = 0, col = 0;
    roles.forEach(r => {
      const span = r.classList.contains('span-5') ? 5 : r.classList.contains('span-3') ? 3 : r.classList.contains('span-2') ? 2 : 1;
      const rr = r.getBoundingClientRect();
      const dt = Math.abs(rr.top - layers[row].top), db = Math.abs(rr.bottom - layers[row + span - 1].bottom);
      worst = Math.max(worst, dt, db);
      row += span; if (row >= layers.length) { row = 0; col++; }
    });
    out.push(col);
  });
  return {worst, columnsComplete: out.every(c => c === 2)} }"""
CARD_SHOTS = {(1680, "gpu-cloud"), (1280, "public-cloud"), (390, "gpu-cloud"), (360, "own-data-center"), (820, "retail-colocation")}


def open_page(b, run, slug, w, h, mobile):
    """New context + page at the given size, with console errors and requests recorded."""
    log, reqs = [], []
    ctx = b.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile,
                        device_scale_factor=2 if w <= 390 else 1)
    pg = ctx.new_page()
    pg.on("console", lambda m: log.append(m.text) if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: log.append(str(e)))
    pg.on("request", lambda r: reqs.append(r.url))
    pg.goto(run.base + slug + ".html")
    pg.wait_for_load_state("networkidle")
    pg.evaluate("document.fonts.ready")
    tag = f"{slug} @{w}"
    check(f"{tag}: no console errors", not log, str(log))
    check(f"{tag}: no third-party requests", not run.third_party(reqs), str(run.third_party(reqs)))
    ow = page_width_overflow(pg)
    check(f"{tag}: no horizontal page scroll", ow <= 0, f"{ow}px")
    return ctx, pg, tag


def suite_cards(b, run):
    for w, h, mobile in WIDTHS:
        for slug in CARDS:
            ctx, pg, tag = open_page(b, run, slug, w, h, mobile)
            st = pg.evaluate("""() => ({cur: document.querySelector('.bm-step[aria-current="page"]')?.dataset.step,
                hrefs: [...document.querySelectorAll('.bm-step')].map(a => a.getAttribute('href')),
                gloss: document.querySelectorAll('[data-g]').length, glossLive: [...document.querySelectorAll('[data-g]')].filter(e => e.tabIndex === 0 && BM_GLOSSARY[e.dataset.g]).length,
                overflowCells: [...document.querySelectorAll('.layer,.role,.crow,.term,.band-col')].filter(e => e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1).length})""")
            check(f"{tag}: header stepper marks this card, links to the 5 card pages",
                  st["cur"] == slug and st["hrefs"] == [s + ".html" for s in CARDS], str(st))
            check(f"{tag}: all glossary tags resolve", st["gloss"] > 0 and st["gloss"] == st["glossLive"], str(st))
            check(f"{tag}: no box overflows its content", st["overflowCells"] == 0, str(st))
            cake = pg.evaluate(CAKE)
            check(f"{tag}: layer cake spans line up with their layers", cake["worst"] < 0.6 and cake["columnsComplete"], str(cake))
            if w in (1680, 360):
                first = pg.locator(".gloss").first
                first.scroll_into_view_if_needed()
                (first.tap() if mobile else first.hover())
                pg.wait_for_timeout(250)
                t = pg.evaluate(TIP)
                check(f"{tag}: tooltip opens fully on screen", tip_on_screen(t), str(t))
                if mobile:
                    pg.locator(".card-note").tap()
                else:
                    pg.mouse.move(2, 2)
                pg.wait_for_timeout(150)
            if (w, slug) in CARD_SHOTS:
                pg.evaluate("window.scrollTo(0,0)")
                run.shot(pg, f"b1_{slug}_{w}_full.png", full_page=True)
            ctx.close()

    # Navigation: hub heading -> card, card stepper -> other card, brand -> hub
    ctx = b.new_context(viewport={"width": 1680, "height": 1000})
    pg = ctx.new_page()
    pg.goto(run.base + "index.html"); pg.wait_for_load_state("networkidle")
    pg.locator("#h-wholesale-colocation a").click(); pg.wait_for_load_state("networkidle")
    check("hub: model heading opens its card", pg.url.endswith("/wholesale-colocation.html"), pg.url)
    pg.locator('.bm-step[data-step="public-cloud"]').click(); pg.wait_for_load_state("networkidle")
    check("card: header stepper opens another card", pg.url.endswith("/public-cloud.html"), pg.url)
    pg.locator(".bm-brand").click(); pg.wait_for_load_state("networkidle")
    check("card: brand link returns to the hub", pg.url.endswith("/business-models/index.html"), pg.url)
    for slug in CARDS:
        r = pg.goto(run.base + slug + ".html")
        check(f"{slug}.html served (200)", r.status == 200, str(r.status))
    ctx.close()


# -- other pages ---------------------------------------------------------------
DOC_BOXES = ".spec-card,.why-card,.headwind,.example,.asset,.fin-risk,.term,.glossary-card,.vc-box,.vc-note,.chip,.pill"
DOC_SHOTS = {(1680, "value-chain"), (1680, "financing"), (1280, "why-finland"), (1680, "specialised-models"), (1680, "glossary"),
             (390, "value-chain"), (390, "financing"), (360, "glossary"), (820, "specialised-models"), (390, "why-finland")}


def suite_pages(b, run):
    for w, h, mobile in WIDTHS:
        for slug in PAGES:
            ctx, pg, tag = open_page(b, run, slug, w, h, mobile)
            st = pg.evaluate(f"""() => {{
                const vis = e => e && e.offsetParent !== null;
                const list = document.querySelector('.bm-pages-list'), menu = document.querySelector('.bm-pages-menu');
                const cur = [...document.querySelectorAll('.bm-pages a[aria-current="page"]')].map(a => a.getAttribute('href'));
                return {{listVisible: vis(list), menuVisible: vis(menu), cur,
                  stepCur: document.querySelector('.bm-step[aria-current]')?.dataset.step || null,
                  gloss: document.querySelectorAll('[data-g]').length, glossLive: [...document.querySelectorAll('[data-g]')].filter(e => e.tabIndex === 0 && BM_GLOSSARY[e.dataset.g]).length,
                  overflow: [...document.querySelectorAll('{DOC_BOXES}')].filter(e => e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1).map(e => e.className + ': ' + e.textContent.trim().slice(0, 30)).slice(0, 4)}} }}""")
            wide = w >= 1280
            check(f"{tag}: header shows {'inline page links' if wide else 'Sivut menu'}", st["listVisible"] == wide and st["menuVisible"] == (not wide), str(st))
            check(f"{tag}: this page marked current in page nav (both copies), no model step current",
                  st["cur"] == [slug + ".html"] * 2 and st["stepCur"] is None, str(st))
            check(f"{tag}: glossary tags resolve", st["gloss"] == st["glossLive"], str(st))
            check(f"{tag}: no box overflows its content", not st["overflow"], str(st["overflow"]))
            if slug == "value-chain":
                # The diagram needs 1100px (desktop layout): it fits from 1280 up and
                # scrolls sideways inside its panel at 1024 and below.
                sc = pg.evaluate("() => { const i=document.querySelector('.vc-wrap .scroll-x__inner'); return {scrolls: i.scrollWidth > i.clientWidth + 1, diagram: Math.round(document.querySelector('.vc-diagram').getBoundingClientRect().width)} }")
                check(f"{tag}: diagram scrolls sideways only when it can't fit (width {sc['diagram']}px)", sc["scrolls"] == (w <= 1024), str(sc))
            if not wide:
                pg.locator(".bm-pages-menu summary").click(); pg.wait_for_timeout(150)
                mv = pg.evaluate("""() => { const u=document.querySelector('.bm-pages-menu ul'); const r=u.getBoundingClientRect();
                    return {open: document.querySelector('.bm-pages-menu').open, l:r.left, r:r.right, vw:document.documentElement.clientWidth} }""")
                check(f"{tag}: Sivut menu opens inside the screen", mv["open"] and mv["l"] >= 0 and mv["r"] <= mv["vw"], str(mv))
                pg.mouse.click(5, h - 5); pg.wait_for_timeout(100)
                check(f"{tag}: Sivut menu closes on outside click", not pg.evaluate("document.querySelector('.bm-pages-menu').open"))
            if st["gloss"] and w in (1680, 360):
                g = pg.locator(".gloss").first; g.scroll_into_view_if_needed()
                (g.tap() if mobile else g.hover()); pg.wait_for_timeout(250)
                t = pg.evaluate(TIP)
                check(f"{tag}: tooltip fully on screen", tip_on_screen(t), str(t))
                pg.mouse.move(2, 2)
            if (w, slug) in DOC_SHOTS:
                pg.evaluate("window.scrollTo(0,0)")
                run.shot(pg, f"b2_{slug}_{w}_full.png", full_page=True)
            ctx.close()

    ctx = b.new_context(viewport={"width": 1680, "height": 1000}); pg = ctx.new_page()
    for slug in ["index"] + CARDS + PAGES:
        r = pg.goto(run.base + slug + ".html"); check(f"{slug}.html served (200)", r.status == 200, str(r.status))
    pg.goto(run.base + "index.html"); pg.wait_for_load_state("networkidle")
    links = pg.evaluate("() => ({vc: document.querySelector('#h-vc a')?.getAttribute('href'), spec: document.querySelector('#h-spec a')?.getAttribute('href'), terms: document.querySelector('.terms-note a')?.getAttribute('href'), pages: [...document.querySelectorAll('.bm-pages-list a')].map(a=>a.getAttribute('href'))})")
    check("hub: panel titles + Termit link to their pages; header lists the 5 pages",
          links["vc"] == "value-chain.html" and links["spec"] == "specialised-models.html" and links["terms"] == "glossary.html"
          and links["pages"] == [s + ".html" for s in PAGES], str(links))
    pg.locator("#h-vc a").click(); pg.wait_for_load_state("networkidle")
    check("hub: value-chain title opens the page", pg.url.endswith("/value-chain.html"), pg.url)
    pg.locator('.bm-pages-list a[href="glossary.html"]').click(); pg.wait_for_load_state("networkidle")
    check("header: page link navigates", pg.url.endswith("/glossary.html"), pg.url)
    pg.goto(run.base + "glossary.html#g-rack"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(300)
    gt = pg.evaluate("() => { const e=document.getElementById('g-rack'); const r=e.getBoundingClientRect(); return {top:r.top, vh:innerHeight, target: e.matches(':target')} }")
    check("glossary: #g-rack deep link scrolls to the card and highlights it", gt["target"] and 0 <= gt["top"] < gt["vh"], str(gt))
    ctx.close()


SUITES = {"hub": suite_hub, "cards": suite_cards, "pages": suite_pages}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://127.0.0.1:8765/business-models/")
    ap.add_argument("--suite", nargs="*", choices=list(SUITES), default=list(SUITES))
    ap.add_argument("--shots", metavar="DIR", help="also save the review screenshots here (e.g. Output/screenshots/business-models)")
    args = ap.parse_args()
    run = Run(args.base, args.shots)
    summary = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name in args.suite:
            print(f"== {name}")
            start = len(results)
            SUITES[name](b, run)
            mine = results[start:]
            summary.append((name, sum(ok for _, ok in mine), len(mine)))
        b.close()
    print()
    for name, ok, n in summary:
        print(f"{'OK  ' if ok == n else 'FAIL'} {name:6} {ok}/{n} checks passed")
    return 0 if all(ok == n for _, ok, n in summary) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())

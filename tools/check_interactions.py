"""Interaction checks for the business-models explainer: chrome, navigation,
glossary tooltips, deep links and swipe behaviour, from 1680px down to 360px.

Four suites (all run by default):
  hub    the hub: tooltips (hover, click-pin, Esc, keyboard focus), stepper and
         deep links, matrix row alignment at 1440/1280/1024, phone swipe track
  cards  the five model cards: stepper, glossary tags, overflow, layer-cake spans
  pages  value chain, financing, specialised models, Why Finland, glossary:
         page nav (inline vs "Sivut" menu), tags, overflow, links between pages
  layers the hub's layered responsibility view (ledger R61): image and overlay,
         who handles each zone per model, demarc lines, tabs (ARIA), side panel,
         markers, the staircase table exactly, reduced motion, phones; the AI Oy
         table without its bar row; no "tarjoaja" anywhere

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

import pw_guard

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
    pw_guard.load(pg, hub)
    pw_guard.settled(pg)
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
    # Hover-only terms (CSP inside the layered view's zone buttons, R69) are left out of the tab order on purpose.
    g = pg.evaluate("""() => ({n:document.querySelectorAll('[data-g]:not(.gloss--hover)').length,
        resolved:[...document.querySelectorAll('[data-g]:not(.gloss--hover)')].every(e=>e.tabIndex===0 && BM_GLOSSARY[e.dataset.g])
          && [...document.querySelectorAll('.gloss--hover[data-g]')].every(e=>e.tabIndex<0 && BM_GLOSSARY[e.dataset.g]),
        total:Object.keys(BM_GLOSSARY).length})""")
    check("glossary: 23 tagged terms all resolve; 75 entries loaded",
          g["n"] == 23 and g["resolved"] and g["total"] == 75, f"{g['n']} tagged, {g['total']} entries")
    ow = page_width_overflow(pg)
    check("desktop 1680: no horizontal page overflow", ow <= 0, f"overflow {ow}px")
    check("desktop: no step current initially", current_step(pg) is None)
    nav = pg.evaluate("""() => ({first: [...document.querySelectorAll('.bm-pages-list a')].map(a => [a.textContent, a.getAttribute('href')])[0],
        cur: [...document.querySelectorAll('.bm-pages a[aria-current="page"]')].map(a => a.textContent)})""")
    check("header: One pager is the first page link and marked current on the hub (both copies)",
          nav["first"] == ["One pager", "./"] and nav["cur"] == ["One pager", "One pager"], str(nav))
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
    pw_guard.load(pg, hub + "#own-data-center")
    pw_guard.settled(pg)
    settle(pg, 400)
    st = pg.evaluate("() => [...document.querySelectorAll('.model.is-active')].map(m=>m.id)")
    check("desktop: deep link #own-data-center selects column 5 + step 5",
          st == ["own-data-center"] and current_step(pg) == "own-data-center", str(st))
    ctx.close()

    # Narrower desktops
    for w in (1440, 1280, 1024):
        ctx = b.new_context(viewport={"width": w, "height": 900})
        pg = ctx.new_page()
        pw_guard.load(pg, hub)
        pw_guard.settled(pg)
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
        pw_guard.load(pg, hub)
        pw_guard.settled(pg)
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
        pw_guard.load(pg, hub + "#own-data-center")
        pw_guard.settled(pg)
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
    pw_guard.load(pg, hub)
    targets = pg.evaluate("() => [...document.querySelectorAll('.bm-header .bm-family')].map(a => a.href)")
    check("header: two family links", len(targets) == 2, str(targets))
    for url in targets:
        r = pw_guard.load(pg, url)
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
    pw_guard.load(pg, run.base + slug + ".html")
    pw_guard.settled(pg)
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
    pw_guard.load(pg, run.base + "index.html"); pw_guard.settled(pg)
    pw_guard.click_to(pg, pg.locator("#h-wholesale-colocation a"))
    check("hub: model heading opens its card", pg.url.endswith("/wholesale-colocation.html"), pg.url)
    pw_guard.click_to(pg, pg.locator('.bm-step[data-step="public-cloud"]'))
    check("card: header stepper opens another card", pg.url.endswith("/public-cloud.html"), pg.url)
    cur = pg.evaluate("() => document.querySelectorAll('.bm-pages a[aria-current]').length")
    check("card: no header page link marked current (One pager is current only on the hub)", cur == 0, str(cur))
    pw_guard.click_to(pg, pg.locator(".bm-brand"))
    check("card: brand link returns to the hub", pg.url.endswith("/business-models/index.html"), pg.url)
    for slug in CARDS:
        r = pw_guard.load(pg, run.base + slug + ".html")
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
        r = pw_guard.load(pg, run.base + slug + ".html"); check(f"{slug}.html served (200)", r.status == 200, str(r.status))
    pw_guard.load(pg, run.base + "index.html"); pw_guard.settled(pg)
    links = pg.evaluate("() => ({vc: document.querySelector('#h-vc a')?.getAttribute('href'), spec: document.querySelector('#h-spec a')?.getAttribute('href'), terms: document.querySelector('.terms-note a')?.getAttribute('href'), pages: [...document.querySelectorAll('.bm-pages-list a')].map(a=>a.getAttribute('href'))})")
    check("hub: panel titles + Termit link to their pages; header lists One pager, then the 5 pages",
          links["vc"] == "value-chain.html" and links["spec"] == "specialised-models.html" and links["terms"] == "glossary.html"
          and links["pages"] == ["./"] + [s + ".html" for s in PAGES], str(links))
    pw_guard.click_to(pg, pg.locator("#h-vc a"))
    check("hub: value-chain title opens the page", pg.url.endswith("/value-chain.html"), pg.url)
    pw_guard.click_to(pg, pg.locator('.bm-pages-list a[href="glossary.html"]'))
    check("header: page link navigates", pg.url.endswith("/glossary.html"), pg.url)
    pw_guard.click_to(pg, pg.locator('.bm-pages-list a[href="./"]'))
    check("header: One pager returns to the hub", pg.url.endswith("/business-models/") and pg.evaluate("document.body.dataset.page") == "hub", pg.url)
    pw_guard.load(pg, run.base + "glossary.html#g-rack"); pw_guard.settled(pg); pg.wait_for_timeout(300)
    gt = pg.evaluate("() => { const e=document.getElementById('g-rack'); const r=e.getBoundingClientRect(); return {top:r.top, vh:innerHeight, target: e.matches(':target')} }")
    check("glossary: #g-rack deep link scrolls to the card and highlights it", gt["target"] and 0 <= gt["top"] < gt["vh"], str(gt))
    ctx.close()


# -- layers: the hub's layered responsibility view (ledger R61) ----------------
# Who handles each zone per model, as the page must show it (Ray's brief v2 with
# his R61 corrections), the demarc gaps and the cloud range.
LAYER_MODELS = ["public-cloud", "gpu-cloud", "retail-colocation", "wholesale-colocation", "own-data-center"]
LAYER_EXPECT = {
    "public-cloud": ({"z1": "own:Itse", "z2": "cp:CSP", "z3": "cp:CSP", "z4": "cp:CSP", "z5": "cp:CSP", "z6": "cp:CSP"},
                     [("g12", "Vastuuraja, tyypillisesti")], True),
    "gpu-cloud": ({"z1": "own:Itse", "z2": "mixed:Itse (bare metal) / GPU-pilvi (hallittu)", "z3": "cp:GPU-pilvi",
                   "z4": "cp:GPU-pilvi", "z5": "cp:GPU-pilvi", "z6": "cp:GPU-pilvi"},
                  [("g23", "Vastuuraja, tyypillisesti")], True),
    "retail-colocation": ({"z1": "own:Itse", "z2": "own:Itse", "z3": "own:Itse", "z4": "cp:Colocation-operaattori",
                           "z5": "cp:Colocation-operaattori", "z6": "cp:Colocation-operaattori"},
                          [("g34", "Vastuuraja")], False),
    "wholesale-colocation": ({"z1": "own:Itse", "z2": "own:Itse", "z3": "own:Itse", "z4": "own:Itse",
                              "z5": "mixed:Turnkey: operaattori · Powered shell: itse", "z6": "cp:Datakeskusoperaattori"},
                             [("g45", "Vastuuraja: turnkey"), ("g56", "Vastuuraja: powered shell")], False),
    "own-data-center": ({z: "own:Itse" for z in ("z1", "z2", "z3", "z4", "z5", "z6")}, [], False),
}
# The staircase, exactly: 14 rows x 5 models (brief cells; R61: row 14 renamed, GPU cell 4 option B).
STAIRS = [
    ("Sovellukset ja tekoälymallit", ["Itse"] * 5),
    ("Data", ["Itse"] * 5),
    ("Käyttöjärjestelmä ja ohjelmistokirjastot", ["Jaettu: IaaS itse, PaaS CSP", "Itse", "Itse", "Itse", "Itse"]),
    ("Virtualisointi ja klusterin hallinta", ["CSP", "Itse (bare metal) / GPU-pilvi (hallittu)", "Itse", "Itse", "Itse"]),
    ("Palvelimet ja tallennus", ["CSP", "GPU-pilvi", "Itse", "Itse", "Itse"]),
    ("Verkkolaitteet", ["CSP", "GPU-pilvi", "Itse", "Itse", "Itse"]),
    ("Räkit ja sähkönsyöttö räkkiin", ["CSP", "GPU-pilvi", "Colocation-operaattori", "Itse", "Itse"]),
    ("Jäähdytys (ilma tai neste)", ["CSP", "GPU-pilvi", "Colocation-operaattori", "Turnkey: operaattori · Powered shell: itse", "Itse"]),
    ("UPS ja varavoima", ["CSP", "GPU-pilvi", "Colocation-operaattori", "Turnkey: operaattori · Powered shell: itse", "Itse"]),
    ("Kulunvalvonta ja fyysinen turvallisuus", ["CSP", "GPU-pilvi", "Colocation-operaattori", "Turnkey: operaattori · Powered shell: itse", "Itse"]),
    ("Tontti ja rakennus", ["CSP", "GPU-pilvi", "Colocation-operaattori", "Datakeskusoperaattori", "Itse"]),
    ("Sähköliittymä ja muuntamo", ["CSP", "GPU-pilvi", "Colocation-operaattori", "Datakeskusoperaattori", "Itse"]),
    ("Sähkön hankinta", ["CSP", "GPU-pilvi", "Colocation-operaattori", "Itse tai läpilaskutettuna", "Itse"]),
    ("Rakennus- ja ympäristöluvat", ["CSP", "GPU-pilvi", "Colocation-operaattori", "Datakeskusoperaattori", "Itse"]),
]
# R69: labels on the lines must keep clear of the callouts' leader lines (sampled along each leader).
LEADER_CLEAR = """() => { const out = [];
  const labels = [...document.querySelectorAll('.lr-line-label, .lr-range-label')].filter(t => t.style.display !== 'none' && t.textContent);
  document.querySelectorAll('.lr-zone .lr-leader').forEach(l => {
    const [x1, y1, x2, y2] = ['x1', 'y1', 'x2', 'y2'].map(a => +l.getAttribute(a));
    labels.forEach(t => { const b = t.getBBox();
      for (let i = 0; i <= 60; i++) { const x = x1 + (x2 - x1) * i / 60, y = y1 + (y2 - y1) * i / 60;
        if (x >= b.x - 2 && x <= b.x + b.width + 2 && y >= b.y - 2 && y <= b.y + b.height + 2) {
          out.push(t.textContent + ' x ' + l.closest('.lr-zone').dataset.zone); break; } } }); });
  return out }"""
# R69: zone names and the one-line description at the top of each zone panel.
ZONE_NAMES = {"z1": "Sovellukset, data ja ohjelmistot", "z2": "Ohjelmistoalusta", "z3": "IT-laitteet",
              "z4": "Salitila ja räkit", "z5": "Rakennuksen tekniikka", "z6": "Kiinteistö ja liittymä"}
ZONE_DESC = {z: t for z, t in [('z1', 'Se, mitä varten kapasiteettia tarvitaan: sovellukset, tekoälymallit, niiden data ja käyttöjärjestelmä.'), ('z2', 'Kerros, joka jakaa laitteiden kapasiteetin käyttöön: virtualisointi ja klusterin hallinta.'), ('z3', 'Laitteet, jotka tekevät varsinaisen laskennan ja tallennuksen: palvelimet, tallennusjärjestelmät ja verkkolaitteet.'), ('z4', 'Tila, johon IT-laitteet asennetaan: räkit, häkit ja sähkönsyöttö räkkiin. Täällä ei itse lasketa mitään.'), ('z5', 'Järjestelmät, jotka pitävät salin käynnissä: jäähdytys, UPS, varavoima ja kulunvalvonta.'), ('z6', 'Tontti, rakennus, sähköliittymä ja muuntamo, sähkön hankinta ja luvat.')]}
# R65: the side panel's default, per model (Ray's texts; three corrected against the cell table, approved 2026-10-21).
LAYER_SUMMARY = {
    "public-cloud": "Yritys hoitaa sovellukset ja datan, IaaS-palvelussa myös käyttöjärjestelmän. Pilvipalveluyhtiö (CSP), esimerkiksi Microsoft, Google tai Amazon, hoitaa kaiken muun virtualisoinnista kiinteistöön.",
    "gpu-cloud": "Yritys hoitaa sovellukset, datan ja käyttöjärjestelmän, bare metal -palvelussa myös klusterin hallinnan. GPU-pilviyhtiö, esimerkiksi CoreWeave, Nebius tai Lambda, hoitaa laitteet, konesalin ja kiinteistön.",
    "retail-colocation": "Yritys omistaa ja hoitaa palvelimensa ja verkkolaitteensa. Colocation-operaattori, esimerkiksi Equinix, Digital Realty tai Telia, hoitaa räkkitilan, sähkön, jäähdytyksen ja kiinteistön.",
    "wholesale-colocation": "Yritys vuokraa kokonaisen salin tai rakennuksen ja kalustaa sen. Turnkey-mallissa operaattori hoitaa jäähdytyksen, UPS:n, varavoiman ja kulunvalvonnan; powered shell -mallissa yritys rakentaa nekin itse. Rakennuksen ja sähköliittymän tarjoaa datakeskusoperaattori, esimerkiksi Digital Realty tai Equinix.",
    "own-data-center": "Yritys hoitaa kaiken tontista sovelluksiin. Verkkoyhtiön (esimerkiksi Fingrid tai Caruna) vastuu päättyy liittymispisteeseen.",
}
PANEL = """() => ({title: (document.querySelector('#lr-detail .zd-title') || {}).textContent,
  summary: (document.querySelector('#lr-detail .zd-summary') || {}).textContent,
  back: (document.querySelector('#lr-detail .zd-back') || {}).textContent || null})"""
# R65: the zone fills by state (computed style), and WCAG contrast of the overlay's labels.
ZONE_FILL = {"own": "rgba(18, 34, 46, 0.5)", "mixed": "lr-hatch", "cp": "rgba(232, 239, 245, 0.4)"}
LAYER_FILLS = """() => Object.fromEntries([...document.querySelectorAll('.lr-zone')].map(g => {
  const cs = getComputedStyle(g.querySelector('.lr-zone-shape')); return [g.dataset.zone, [cs.fill, cs.stroke]] }))"""
# Worst case: each label's backing (box or halo) composited over black, the darkest the picture or a fill can be.
LABEL_CONTRAST = """() => {
  const rgba = s => { const m = s.match(/[\\d.]+/g).map(Number); return [m[0], m[1], m[2], m.length > 3 ? m[3] : 1] };
  const over = (c, b) => [0, 1, 2].map(i => c[i] * c[3] + b[i] * (1 - c[3]));
  const lum = c => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4) };
                     return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2]) };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05) };
  const out = [];
  document.querySelectorAll('.lr-zone').forEach(g => {
    const box = over(rgba(getComputedStyle(g.querySelector('.lr-label-box')).fill), [0, 0, 0]);
    ['.lr-label-name', '.lr-label-who'].forEach(s => out.push([g.dataset.zone + s,
      ratio(over(rgba(getComputedStyle(g.querySelector(s)).fill), box), box)]));
  });
  document.querySelectorAll('.lr-line-label, .lr-range-label').forEach(t => {
    if (t.style.display === 'none') return;
    const cs = getComputedStyle(t), halo = over(rgba(cs.stroke), [0, 0, 0]);
    out.push([t.getAttribute('class') + ':' + t.textContent, ratio(over(rgba(cs.fill), halo), halo)]);
  });
  return out }"""
LAYER_STATE = """() => {
  const D = window.BM_LAYERS;
  const zones = Object.fromEntries([...document.querySelectorAll('.lr-zone')].map(g => [g.dataset.zone,
    (g.classList.contains('is-own') ? 'own' : g.classList.contains('is-mixed') ? 'mixed' : 'cp') + ':' + g.querySelector('.lr-label-who').textContent]));
  const lines = [...document.querySelectorAll('.lr-lines .lr-line')].filter(l => l.style.display !== 'none')
    .map((l, i) => ({pts: l.getAttribute('points'), label: document.querySelectorAll('.lr-lines .lr-line-label')[i].textContent}));
  const range = document.querySelector('.lr-range').style.display !== 'none';
  const sel = [...document.querySelectorAll('.layers-tab')].filter(t => t.getAttribute('aria-selected') === 'true').map(t => t.dataset.model);
  const list = Object.fromEntries([...document.querySelectorAll('.zone-btn')].map(b => [b.dataset.zone, b.querySelector('.zone-who').textContent]));
  return {zones, lines, range, sel, list, cloudNote: !document.getElementById('lr-cloud-note').hidden,
          gap: Object.fromEntries(Object.entries(D.gaps).map(([k, v]) => [k, v.map(p => p.join(',')).join(' ')]))} }"""


def suite_layers(b, run):
    hub = run.base + "index.html"
    log = []
    ctx = b.new_context(viewport={"width": 1680, "height": 1050})
    pg = ctx.new_page()
    instrument(pg, log)
    pw_guard.load(pg, hub)
    pw_guard.settled(pg)
    pg.evaluate("document.fonts.ready")
    st = pg.evaluate("""() => {
      const sec = document.getElementById('kerrokset'), path = document.querySelector('.path'), m = document.getElementById('matrix');
      const img = sec.querySelector('.layers-stage img'), svg = sec.querySelector('.layers-svg');
      const bridge = document.querySelector('.layers-bridge');
      const before = (a, b) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
      const D = window.BM_LAYERS;
      return {order: before(sec, bridge) && before(bridge, path) && before(path, m),
              title: sec.querySelector('h2').textContent, bridge: bridge.textContent,
              img: [img.currentSrc.split('/').pop(), img.naturalWidth, img.naturalHeight, img.complete], alt: img.alt,
              viewBox: svg.getAttribute('viewBox'), data: [D.width, D.height],
              polys: [...svg.querySelectorAll('.lr-zone')].every(g => g.querySelector('polygon').getAttribute('points') ===
                     D.zones[g.dataset.zone].poly.map(p => p.join(',')).join(' ')),
              zoneA11y: [...svg.querySelectorAll('.lr-zone')].map(g => [g.dataset.zone, g.tabIndex, g.getAttribute('role')]),
              markers: [...svg.querySelectorAll('.lr-marker')].map(g => [g.dataset.marker, g.tabIndex, g.getAttribute('role')]),
              tabs: [...sec.querySelectorAll('[role=tab]')].map(t => [t.textContent, t.getAttribute('aria-controls')]),
              live: document.getElementById('lr-detail').getAttribute('aria-live'),
              stairsHidden: document.getElementById('lr-stairs').hidden,
              toggle: [sec.querySelector('.stairs-toggle').textContent, sec.querySelector('.stairs-toggle').getAttribute('aria-expanded')]} }""")
    check("layers: section, then the bridge sentence, then the AI Oy growth path and table",
          st["order"] and st["title"] == "Mitä yritys hoitaa itse ja mitä se ostaa"
          and st["bridge"].startswith("Yllä rakenne yleisesti. Alla samat mallit kuvitteellisen AI Oy:n kasvupolkuna"), str(st["title"]))
    check("layers: the WebP image (1672x941) loaded, with Finnish alt text",
          st["img"] == ["datakeskus-kerrokset.webp", 1672, 941, True] and st["alt"].startswith("Läpileikkauskuva")
          and len(st["alt"]) > 200, str(st["img"]))
    check("layers: the overlay's viewBox is the image's pixel size and matches the data file",
          st["viewBox"] == "0 0 1672 941" and st["data"] == [1672, 941], st["viewBox"])
    check("layers: six zone polygons exactly as measured in kerrokset-data.js", st["polys"] and len(st["zoneA11y"]) == 6)
    check("layers: zones and both markers are keyboard-focusable buttons",
          all(t == 0 and r == "button" for _, t, r in st["zoneA11y"]) and [m[0] for m in st["markers"]] == ["grid", "heat"]
          and all(t == 0 and r == "button" for _, t, r in st["markers"]), str(st["zoneA11y"] + st["markers"]))
    check("layers: five model tabs in the table's order, each controlling the panel",
          [t for t, _ in st["tabs"]] == ["Julkinen pilvi", "GPU-pilvi", "Retail-colocation", "Wholesale-colocation", "Oma datakeskus"]
          and all(c == "lr-panel" for _, c in st["tabs"]), str(st["tabs"]))
    bars = pg.evaluate("""() => [...document.querySelectorAll('.layers-tab')].map(t => { const b = t.querySelector('.lr-tab-bar');
        return [t.dataset.model, b && b.getAttribute('aria-hidden'), b ? [...b.children].map(s => s.className.replace('is-', '')) : []] })""")
    want_bars = [[m, "true", [v.split(":")[0] for _, v in sorted(LAYER_EXPECT[m][0].items())]] for m in LAYER_MODELS]
    names = [pg.get_by_role("tab", name=n, exact=True).count() for n in
             ["Julkinen pilvi", "GPU-pilvi", "Retail-colocation", "Wholesale-colocation", "Oma datakeskus"]]
    check("layers: each tab has its model's 6-segment bar (Z1 on top, Itse dark, shared hatched), aria-hidden; tab names unchanged (R65)",
          bars == want_bars and names == [1] * 5, f"{bars} {names}")
    check("layers: the side panel is announced (aria-live polite)", st["live"] == "polite")
    check("layers: the staircase is collapsed by default behind its control",
          st["stairsHidden"] and st["toggle"] == ["Näytä kaikki mallit rinnakkain", "false"], str(st["toggle"]))

    # Every model: zones, labels, the list, the demarc line(s), the range and the cloud note.
    for m in LAYER_MODELS:
        pg.locator(f"#lr-tab-{m}").click()
        settle(pg, 1000)    # the last zone's fill starts 400ms late (R65 stagger) and takes 350ms
        s = pg.evaluate(LAYER_STATE)
        zones, lines, rng = LAYER_EXPECT[m]
        got_lines = [(l["pts"], l["label"]) for l in s["lines"]]
        want_lines = [(s["gap"][g], label) for g, label in lines]
        check(f"layers {m}: zones and labels show who handles each (Itse strong, counterparty named)",
              s["zones"] == zones and s["sel"] == [m], str(s["zones"]))
        check(f"layers {m}: the zone list says the same", {z: v.split(":", 1)[1] for z, v in zones.items()} == s["list"], str(s["list"]))
        check(f"layers {m}: demarc line(s) in the right gap(s), labelled", got_lines == want_lines, str(got_lines))
        check(f"layers {m}: the range band and the shared-responsibility note only for the cloud models",
              s["range"] == rng and s["cloudNote"] == rng, f"range {s['range']}, note {s['cloudNote']}")
        pn = pg.evaluate(PANEL)
        tab = pg.locator(f"#lr-tab-{m}").inner_text().strip()
        check(f"layers {m}: with nothing selected the side panel shows the model's summary, no back button (R65)",
              pn == {"title": tab, "summary": LAYER_SUMMARY[m], "back": None}, str(pn))
        fills = pg.evaluate(LAYER_FILLS)
        check(f"layers {m}: zone fills match the legend (Itse navy, shared hatched, counterparty light), no outline at rest (R65)",
              all(ZONE_FILL[v.split(":")[0]] in fills[z][0] and fills[z][1] in ("none", "rgba(0, 0, 0, 0)") for z, v in zones.items()),
              str(fills))
        if rng:
            band = pg.evaluate("""(m) => { const D = window.BM_LAYERS, r = document.querySelector('.lr-range'), [a, b] = D.models[m].range;
                const p = q => q.map(x => x.join(',')).join(' ');
                return [r.getAttribute('points') === p(D.gaps[a].concat(D.gaps[b].slice().reverse())), getComputedStyle(r).fill,
                        getComputedStyle(r).stroke, document.querySelectorAll('.lr-range-edge').length] }""", m)
            check(f"layers {m}: the range is a light shaded band from the typical line to the range end, no dotted line (R65)",
                  band == [True, "rgba(251, 234, 220, 0.55)", "none", 0], str(band))
        pos = pg.evaluate("""() => ({pos: [...document.querySelectorAll('.lr-pos-label')].filter(t => t.style.display !== 'none')
            .map(t => [t.textContent, t.dataset.gap]), range: [...document.querySelectorAll('.lr-range-label:not(.lr-pos-label)')]
            .filter(t => t.style.display !== 'none').map(t => t.textContent)})""")
        want_pos = {"public-cloud": {"pos": [["IaaS", "g12"], ["PaaS", "g1x"], ["SaaS", "g1t"]], "range": []},
                    "gpu-cloud": {"pos": [], "range": ["hallittu palvelu"]}}.get(m, {"pos": [], "range": []})
        check(f"layers {m}: public cloud names IaaS (Z1/Z2 line), PaaS (inside Z1) and SaaS (top) on its band; GPU cloud keeps 'hallittu palvelu' (R66)",
              pos == want_pos, str(pos))
        hits = pg.evaluate(LEADER_CLEAR)
        check(f"layers {m}: no demarc or band label sits on a callout's leader line (R69)", hits == [], str(hits))
        con = pg.evaluate(LABEL_CONTRAST)
        check(f"layers {m}: every label on the picture has contrast >= 4.5 against its box or halo, even over black (R65)",
              len(con) >= 12 and min(r for _, r in con) >= 4.5, str(sorted(con, key=lambda c: c[1])[:3]))

    # R65: the dark (Itse) share is the top of the building and grows downwards from tab to tab.
    owns = [[z for z, v in sorted(LAYER_EXPECT[m][0].items()) if v.startswith("own:")] for m in LAYER_MODELS]
    check("layers: across the tabs the Itse zones are always the top ones, and their count only grows (1, 1, 3, 4, 6)",
          [len(o) for o in owns] == [1, 1, 3, 4, 6] and all(o == ["z%d" % (i + 1) for i in range(len(o))] for o in owns), str(owns))
    pg.locator("#lr-tab-public-cloud").click()
    settle(pg, 900)
    pg.locator("#lr-tab-own-data-center").click()
    down = pg.evaluate("[...document.querySelectorAll('.lr-zone-shape')].map(s => parseFloat(getComputedStyle(s).transitionDelay))")
    settle(pg, 900)
    pg.locator("#lr-tab-public-cloud").click()
    up = pg.evaluate("[...document.querySelectorAll('.lr-zone-shape')].map(s => parseFloat(getComputedStyle(s).transitionDelay))")
    settle(pg, 900)
    check("layers: switching tabs fills the zones top-down when the Itse share grows, bottom-up when it shrinks",
          down == sorted(down) and down[0] < down[-1] and up == sorted(up, reverse=True) and up[0] > up[-1], f"{down} {up}")

    # R66: the band's IaaS/PaaS/SaaS labels and the cloud note's terms open their glossary entries.
    pg.locator("#lr-tab-public-cloud").click()
    settle(pg, 900)
    keys = pg.evaluate("""() => [[...document.querySelectorAll('.lr-pos-label')].map(t => t.dataset.g),
        [...document.querySelectorAll('#lr-cloud-note .gloss')].map(s => s.dataset.g)]""")
    pg.locator(".lr-pos-label[data-g=paas]").click()
    settle(pg, 150)
    tip_click = pg.evaluate("() => { const t = document.getElementById('gloss-tip'); return t && !t.hidden ? t.querySelector('.gloss-tip-term').textContent : null }")
    pg.keyboard.press("Escape")
    pg.locator(".lr-pos-label[data-g=saas]").focus()
    settle(pg, 100)
    tip_focus = pg.evaluate("() => { const t = document.getElementById('gloss-tip'); return t && !t.hidden ? t.querySelector('.gloss-tip-term').textContent : null }")
    pg.keyboard.press("Enter")
    settle(pg, 100)
    pg.keyboard.press("Escape")
    check("layers: IaaS, PaaS and SaaS on the band and in the cloud note link to their glossary entries (click, focus, Enter) (R66)",
          keys == [["iaas", "paas", "saas"], ["iaas", "paas", "saas"]] and tip_click == "PaaS" and tip_focus == "SaaS",
          f"{keys} {tip_click} {tip_focus}")

    # R69: CSP in the callouts and the zone list explains itself on hover; a click still selects the zone.
    tipterm = "() => { const t = document.getElementById('gloss-tip'); return t && !t.hidden ? t.querySelector('.gloss-tip-term').textContent : null }"
    marks = pg.evaluate("""() => [[...document.querySelectorAll('.lr-label-who.gloss--hover')].map(t => t.closest('.lr-zone').dataset.zone + ':' + t.dataset.g + ':' + t.tabIndex),
        [...document.querySelectorAll('.zone-who.gloss--hover')].map(t => t.closest('.zone-btn').dataset.zone + ':' + t.dataset.g + ':' + t.tabIndex)]""")
    pg.locator(".zone-btn[data-zone=z3] .zone-who").hover()
    settle(pg, 250)
    hov = pg.evaluate(tipterm)
    pg.locator(".zone-btn[data-zone=z3] .zone-who").click()
    settle(pg, 200)
    sel = pg.evaluate("""() => [document.querySelector('.zone-btn[data-zone=z3]').getAttribute('aria-pressed'),
        (document.querySelector('#lr-detail .zd-who .gloss') || {}).dataset, (document.querySelector('#lr-detail .zd-who .gloss') || {}).tabIndex]""")
    pinned = pg.evaluate("() => !document.getElementById('gloss-tip').hidden && !document.querySelector('.zone-btn[data-zone=z3] .zone-who:hover')")
    pg.mouse.move(5, 5)
    pg.locator("#lr-detail .zd-back").click()
    settle(pg, 200)
    want = ["z2", "z3", "z4", "z5", "z6"]
    check("layers: CSP in the callouts and zone list shows its glossary tooltip on hover, stays out of the tab order, and a click selects the zone; the panel's CSP is focusable (R69)",
          marks == [[z + ":csp:-1" for z in want], [z + ":csp:-1" for z in want]] and hov == "CSP" and sel[0] == "true"
          and sel[1] == {"g": "csp"} and sel[2] == 0 and not pinned, f"{marks} {hov} {sel} {pinned}")

    # The line slides between gaps; with reduced motion it jumps.
    pg.locator("#lr-tab-public-cloud").click()
    settle(pg, 650)
    pg.locator("#lr-tab-retail-colocation").click()
    settle(pg, 120)
    mid = pg.evaluate(LAYER_STATE)
    check("layers: the demarc line slides (mid-way 120ms after switching)",
          mid["lines"] and mid["lines"][0]["pts"] not in (mid["gap"]["g12"], mid["gap"]["g34"]), str(mid["lines"][:1]))
    settle(pg, 600)

    # Keyboard: WAI-ARIA tabs.
    pg.locator("#lr-tab-public-cloud").click()
    settle(pg, 600)
    pg.locator("#lr-tab-public-cloud").focus()
    pg.keyboard.press("ArrowRight")
    settle(pg, 100)
    k1 = pg.evaluate("[document.activeElement.id, document.querySelector('[role=tab][aria-selected=true]').id, document.activeElement.tabIndex]")
    pg.keyboard.press("End")
    settle(pg, 100)
    k2 = pg.evaluate("document.querySelector('[role=tab][aria-selected=true]').id")
    pg.keyboard.press("Home")
    settle(pg, 100)
    k3 = pg.evaluate("document.querySelector('[role=tab][aria-selected=true]').id")
    pg.keyboard.press("ArrowLeft")
    settle(pg, 100)
    k4 = pg.evaluate("document.querySelector('[role=tab][aria-selected=true]').id")
    tabidx = pg.evaluate("[...document.querySelectorAll('[role=tab]')].map(t => t.tabIndex)")
    check("layers: tabs follow the ARIA pattern (arrows, Home, End; only the selected tab is in the tab order)",
          k1 == ["lr-tab-gpu-cloud", "lr-tab-gpu-cloud", 0] and k2 == "lr-tab-own-data-center" and k3 == "lr-tab-public-cloud"
          and k4 == "lr-tab-own-data-center" and tabidx == [-1, -1, -1, -1, 0], f"{k1} {k2} {k3} {k4} {tabidx}")

    # A zone opens its rows in the side panel, from the staircase.
    pg.locator("#lr-tab-retail-colocation").click()
    settle(pg, 650)
    lab = pg.locator(".lr-zone[data-zone=z4]").get_attribute("aria-label")
    check("layers: zone labels describe the selected model, e.g. 'Salitila ja räkit: Colocation-operaattori hoitaa'",
          lab == "Salitila ja räkit: Colocation-operaattori hoitaa", lab)
    pg.locator(".lr-zone[data-zone=z6]").focus()
    pg.keyboard.press("Enter")
    settle(pg, 200)
    d = pg.evaluate("""() => ({title: document.querySelector('#lr-detail .zd-title').textContent,
        rows: [...document.querySelectorAll('#lr-detail .zd-rows li')].map(li => [...li.children].map(c => c.textContent)),
        notes: [...document.querySelectorAll('#lr-detail .zd-note')].map(p => p.textContent),
        pressed: [document.querySelector('.lr-zone[data-zone=z6]').getAttribute('aria-pressed'),
                  document.querySelector('.zone-btn[data-zone=z6]').getAttribute('aria-pressed')]})""")
    check("layers: Enter on a zone opens its rows and who handles each (retail, Kiinteistö ja liittymä)",
          d["title"] == "Kiinteistö ja liittymä" and d["rows"] == [[n, c[2]] for n, c in STAIRS[10:14]] and d["pressed"] == ["true", "true"],
          str(d))
    descs = {}
    for z in ("z1", "z2", "z3", "z4", "z5", "z6"):
        pg.locator(f".zone-btn[data-zone={z}]").click()
        settle(pg, 120)
        descs[z] = pg.evaluate("""() => { const t = document.querySelector('#lr-detail .zd-title'), d = document.querySelector('#lr-detail .zd-desc');
            return [t && t.textContent, d && d.textContent, d && t && t.nextElementSibling === d] }""")
    check("layers: each zone panel opens with its one-line description under the title; Z3 and Z4 renamed (R69)",
          descs == {z: [n, ZONE_DESC[z], True] for z, n in ZONE_NAMES.items()}, str(descs))
    pg.locator(".lr-zone[data-zone=z6]").focus()
    pg.keyboard.press("Enter")
    settle(pg, 200)
    sc = pg.evaluate("""() => [getComputedStyle(document.querySelector('.lr-zone.is-selected .lr-zone-shape')).stroke,
        getComputedStyle(document.querySelector('.zone-btn[aria-pressed=true]')).boxShadow,
        getComputedStyle(document.querySelector('.lr-zone.is-selected .lr-zone-halo')).stroke]""")
    check("layers: the selected zone's outline and the selected list item share one accent colour, blue, each with a white gap or halo (R69, R70)",
          sc[0] == "rgb(31, 78, 110)" and sc[1] == "rgb(255, 255, 255) 0px 0px 0px 2px, rgb(31, 78, 110) 0px 0px 0px 5px"
          and sc[2] == "rgba(255, 255, 255, 0.9)", str(sc))
    check("layers: the panel shows the zone's footnotes (connection point; retail electricity billing)",
          d["notes"] == ["Verkkoyhtiö vastaa verkosta liittymispisteeseen asti.",
                         "Sähkö laskutetaan yleensä operaattorin laskulla (kW tai kWh)."], str(d["notes"]))
    bk = pg.evaluate(PANEL)["back"]
    pg.locator("#lr-detail .zd-back").click()
    settle(pg, 200)
    after = pg.evaluate("""() => ({...(""" + PANEL + """)(), focus: document.activeElement.id,
        pressed: [...document.querySelectorAll('.lr-zone, .zone-btn, .lr-marker, .marker-btn')].filter(e => e.getAttribute('aria-pressed') === 'true').length})""")
    check("layers: an open zone has '← Takaisin yhteenvetoon'; it returns to the model's summary, clears the selection and keeps focus in the panel (R65)",
          bk == "← Takaisin yhteenvetoon" and after["summary"] == LAYER_SUMMARY["retail-colocation"] and after["back"] is None
          and after["pressed"] == 0 and after["focus"] == "lr-detail", f"{bk} {after}")
    pg.locator("#lr-tab-gpu-cloud").click()
    settle(pg, 650)
    # Regression (R61): the demarc layer and the range band sat over the zones and took their clicks.
    try:
        pg.locator(".lr-zone[data-zone=z2] .lr-zone-shape").click(timeout=3000)
        settle(pg, 200)
        through = pg.evaluate("document.querySelector('.lr-zone[data-zone=z2]').getAttribute('aria-pressed')") == "true"
    except Exception as e:
        through = False
    check("layers: a click on a zone under the range band reaches the zone (lines never take clicks)", through)
    pg.locator(".zone-btn[data-zone=z2]").click()
    settle(pg, 200)
    n2 = pg.evaluate("[...document.querySelectorAll('#lr-detail .zd-note')].length")
    x2 = pg.evaluate("document.querySelectorAll('#lr-detail .zd-extra').length")
    pg.locator(".zone-btn[data-zone=z5]").click()
    settle(pg, 200)
    n5 = pg.evaluate("[...document.querySelectorAll('#lr-detail .zd-note')].map(p => p.textContent)")
    check("layers: the GPU cloud's data-centre footnote shows on the building zones only",
          n2 == 0 and n5 == ["GPU-pilvi voi toimia omassa tai colocation-operaattorin datakeskuksessa."], f"{n2} {n5}")
    x5 = pg.evaluate("""() => ({text: [...document.querySelectorAll('#lr-detail .zd-extra')].map(p => p.textContent),
        src: [...document.querySelectorAll('#lr-detail .zd-src a')].map(a => a.textContent)})""")
    check("layers: Z5 (Rakennuksen tekniikka) explains redundancy with its sources, and only Z5 (R64)",
          x2 == 0 and len(x5["text"]) == 1 and x5["text"][0].startswith("Kahdennus: sähkönsyöttö, UPS, varavoima ja jäähdytys")
          and "N+1 tai 2N" in x5["text"][0] and x5["src"] == ["Uptime Institute", "CoreSite", "Cushman & Wakefield (2026)"], f"{x2} {x5}")

    # Row <-> zone highlight.
    pg.locator(".stairs-toggle").click()
    settle(pg, 200)
    tg = pg.evaluate("[document.querySelector('.stairs-toggle').textContent, document.querySelector('.stairs-toggle').getAttribute('aria-expanded'), document.getElementById('lr-stairs').hidden]")
    check("layers: the control opens the staircase and changes its label", tg == ["Piilota rinnakkaisnäkymä", "true", False], str(tg))
    table = pg.evaluate("""() => ({head: [...document.querySelectorAll('.stairs-table thead th')].map(th => th.childNodes[0].textContent.trim()),
        rows: [...document.querySelectorAll('.stairs-table tbody tr[data-row]')].map(tr => {
          const t = el => { const c = el.cloneNode(true); c.querySelectorAll('.fn').forEach(f => f.remove()); return c.textContent.trim(); };
          return [t(tr.querySelector('th')), [...tr.querySelectorAll('td')].map(t)] }),
        groups: [...document.querySelectorAll('.stairs-group th')].map(th => th.textContent),
        own: [...document.querySelectorAll('.stairs-table td')].every(td => (td.textContent.trim() === 'Itse') === td.classList.contains('own'))})""")
    check("layers: the staircase has exactly the brief's 14 rows x 5 models (with the R61 corrections)",
          table["rows"] == [[n, c] for n, c in STAIRS] and table["head"] == ["Julkinen pilvi", "GPU-pilvi", "Retail-colocation",
                                                                          "Wholesale-colocation", "Oma datakeskus"],
          str([r for r, w in zip(table["rows"], STAIRS) if r != [w[0], w[1]]][:2]))
    grid = pg.evaluate("""() => { const heads = [...document.querySelectorAll('.stairs-table thead th[data-model]')];
        const models = heads.map(th => th.dataset.model), out = Object.fromEntries(models.map(m => [m, []]));
        document.querySelectorAll('.stairs-table tbody tr[data-row]').forEach(tr => [...tr.querySelectorAll('td')].forEach((td, i) => {
          if (td.classList.contains('demarc-top')) out[models[i]].push(+tr.dataset.row) }));
        const D = window.BM_LAYERS, img = {};
        Object.keys(D.models).forEach(m => img[m] = D.models[m].lines.map(([g]) => D.zones['z' + g.slice(-1)].rows[0]));
        const cs = getComputedStyle(document.querySelector('.stairs-table td.demarc-top'));
        const w = heads.map(th => th.getBoundingClientRect().width);
        const tk = document.querySelector('.stairs-table tr[data-row="8"]').children[4].querySelectorAll('.sc-line');
        return {grid: out, img, style: [cs.borderTopStyle, cs.borderTopWidth, cs.borderTopColor], spread: Math.max(...w) - Math.min(...w),
                twoLines: tk.length === 2 && tk[1].getBoundingClientRect().top > tk[0].getBoundingClientRect().top} }""")
    want_dm = {"public-cloud": [4], "gpu-cloud": [5], "retail-colocation": [7], "wholesale-colocation": [8, 11], "own-data-center": []}
    check("layers: the grid draws the vastuuraja as a rust dashed top edge at each model's step, where the picture draws it (R73)",
          grid["grid"] == want_dm and grid["img"] == want_dm and grid["style"] == ["dashed", "3px", "rgb(180, 86, 26)"], str(grid))
    check("layers: the five model columns are equally wide; wholesale's turnkey/powered-shell cells take two lines (R73)",
          grid["spread"] <= 1 and grid["twoLines"], str(grid))
    selc = {}
    for m in ("public-cloud", "wholesale-colocation"):
        pg.locator(f"#lr-tab-{m}").click()
        settle(pg, 300)
        selc[m] = pg.evaluate("""() => { const ths = [...document.querySelectorAll('.stairs-table thead th[data-model]')];
            const col = [...document.querySelectorAll('.stairs-table td.is-col')];
            return {heads: ths.filter(th => th.classList.contains('is-col')).map(th => th.dataset.model),
                    headBg: getComputedStyle(document.querySelector('.stairs-table thead th.is-col')).backgroundColor,
                    cells: col.length, edges: [...new Set(col.map(td => getComputedStyle(td).boxShadow))],
                    rust: [...document.querySelectorAll('.stairs-table td')].some(td => /180, 86, 26/.test(getComputedStyle(td).boxShadow))} }""")
    check("layers: the selected model is marked once in blue: navy header, blue side edges on its 14 cells, no rust boxes (R73)",
          all(v["heads"] == [m] and v["headBg"] == "rgb(18, 34, 46)" and v["cells"] == 14 and not v["rust"]
              and v["edges"] == ["rgb(31, 78, 110) -2px 0px 0px 0px, rgb(31, 78, 110) 2px 0px 0px 0px"] for m, v in selc.items()), str(selc))
    check("layers: five layer groups, and every 'Itse' cell (only those) has the strong fill",
          table["groups"] == ["SOVELLUKSET JA DATA", "ALUSTA", "LAITTEET", "KONESALI", "KIINTEISTÖ JA ENERGIA"] and table["own"],
          str(table["groups"]))
    pg.locator(".stairs-table tr[data-row='8']").hover()
    settle(pg, 150)
    hot = pg.evaluate("[...document.querySelectorAll('.lr-zone.is-hot')].map(g => g.dataset.zone)")
    pg.mouse.move(5, 5)
    pg.locator(".lr-zone[data-zone=z3] .lr-label-box").hover()
    settle(pg, 150)
    rows_hot = pg.evaluate("[...document.querySelectorAll('.stairs-table tr.is-hot')].map(tr => tr.dataset.row)")
    check("layers: hovering a staircase row lights its zone, and a zone its rows", hot == ["z5"] and rows_hot == ["5", "6"], f"{hot} {rows_hot}")
    note = pg.evaluate("""() => [document.querySelector('.stairs-note > p').textContent,
        [...document.querySelectorAll('.stairs-note li')].map(li => li.textContent)]""")
    check("layers: the note under the staircase is a lead sentence and a four-item list (R61 wording; R69 list)",
          note == ["Kerrokset eivät näytä kaikkia eroja.", ["Julkinen pilvi ja GPU-pilvi: ero on ennen kaikkea sitoumuksessa. GPU-pilvessä kapasiteetti varataan usein omaan käyttöön monivuotisella sopimuksella.", "Retail ja wholesale: ero on mittakaavassa ja sopimuksessa. Wholesale on kokonainen sali tai rakennus 5–15 vuoden vuokrasopimuksella.", "Retail-colocationin arvoa lisää myös verkkoekosysteemi: samassa rakennuksessa toimivat operaattorit ja pilvipalvelut, joihin voi kytkeytyä suoraan (cross-connect). Wholesale-asiakkaalle tärkeämpiä ovat sähkökapasiteetti ja jäähdytys.", "Pilvimalleissa vastuuraja riippuu myös ostetusta palvelusta."]], str(note))
    key = pg.evaluate("[...document.querySelectorAll('.lr-key')].map(k => k.textContent)")
    check("layers: the legend's hatched key reads 'Jaettu tai riippuu palvelusta tai sopimuksesta' (R69)",
          key == ["Itse", "Jaettu tai riippuu palvelusta tai sopimuksesta", "Vastapuoli", "Vastuuraja"], str(key))

    # Markers: the connection point (every model) and the waste-heat hotspot.
    vis = []
    for m in LAYER_MODELS:
        pg.locator(f"#lr-tab-{m}").click()
        settle(pg, 500)
        vis.append(pg.evaluate("getComputedStyle(document.querySelector('.lr-marker--grid')).display !== 'none'"))
    mb = pg.evaluate("""() => { const zb = getComputedStyle(document.querySelector('.lr-zone .lr-label-box')).fill;
        return [...document.querySelectorAll('.lr-marker')].map(g => { const box = g.querySelector('.lr-marker-box'), b = box.getBBox();
          const t = [...g.querySelectorAll('.lr-marker-label, .lr-marker-sub')].map(e => e.getBBox());
          return [g.dataset.marker, b.width > 0 && t.every(r => r.x >= b.x && r.y >= b.y && r.x + r.width <= b.x + b.width
                  && r.y + r.height <= b.y + b.height), getComputedStyle(box).fill === zb] }) }""")
    check("layers: the connection-point and waste-heat labels sit in white boxes like the zone callouts (R65)",
          mb == [["grid", True, True], ["heat", True, True]], str(mb))
    pg.locator(".lr-marker--grid .lr-marker-ring").click()
    settle(pg, 200)
    gd = pg.evaluate("document.getElementById('lr-detail').textContent")
    check("layers: the connection-point marker is there in every model and says where the network company's responsibility ends",
          all(vis) and "Liittymispiste: verkkoyhtiön vastuu päättyy tähän." in gd, gd[:120])
    pg.locator(".lr-marker--heat .lr-marker-ring").click()
    settle(pg, 200)
    hd = pg.evaluate("""() => ({text: document.getElementById('lr-detail').textContent,
        links: [...document.querySelectorAll('#lr-detail a')].map(a => a.getAttribute('href'))})""")
    check("layers: the waste-heat hotspot: Mäntsälä since 2015 (Yandex, now Nebius), Microsoft and Fortum, link to the specialised models page",
          "Mäntsälän datakeskus on myynyt hukkalämpöä paikalliseen kaukolämpöverkkoon vuodesta 2015" in hd["text"] and "Nebius" in hd["text"]
          and "Fortumin" in hd["text"] and "specialised-models.html#hukkalampo" in hd["links"], str(hd["links"]))
    check("layers: the Fortum source is the ecosystem page's own",
          "https://www.fortum.com/en/media/2026/05/fortum-has-started-heat-production-two-large-data-centre-sites-finland" in hd["links"])
    errs = [l for l in log if l[0] in ("console", "pageerror")]
    check("layers: no console errors/warnings or page errors", not errs, str(errs))
    run.shot(pg, "l1_layers_1680.png", full_page=True)
    ctx.close()

    # Reduced motion: the line jumps.
    ctx = b.new_context(viewport={"width": 1680, "height": 1050}, reduced_motion="reduce")
    pg = ctx.new_page()
    pw_guard.load(pg, hub)
    pw_guard.settled(pg)
    pg.locator("#lr-tab-wholesale-colocation").click()
    settle(pg, 30)
    s = pg.evaluate(LAYER_STATE)
    check("layers: with reduced motion the line jumps to its gap at once",
          [l["pts"] for l in s["lines"]] == [s["gap"]["g45"], s["gap"]["g56"]], str(s["lines"]))
    ctx.close()

    # The waste-heat link lands on its card.
    ctx = b.new_context(viewport={"width": 1680, "height": 1050})
    pg = ctx.new_page()
    pw_guard.load(pg, run.base + "specialised-models.html#hukkalampo")
    pw_guard.settled(pg)
    settle(pg, 300)
    ht = pg.evaluate("() => { const e = document.getElementById('hukkalampo'); const r = e && e.getBoundingClientRect(); return e && [e.querySelector('h3').textContent, r.top >= 0 && r.top < innerHeight] }")
    check("layers: specialised-models.html#hukkalampo lands on 'Hukkalämmön myynti'", ht == ["Hukkalämmön myynti", True], str(ht))
    ctx.close()

    # Phones and the layouts between: no sideways scroll; on phones the labels give way to the zone list.
    for w, h, mobile in WIDTHS:
        ctx = b.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile)
        pg = ctx.new_page()
        pw_guard.load(pg, hub)
        pw_guard.settled(pg)
        ph = pg.evaluate("""() => { const st = document.querySelector('.layers-stage').getBoundingClientRect(), side = document.querySelector('.layers-side').getBoundingClientRect();
            const lab = document.querySelector('.lr-label'); return {below: side.top >= st.bottom - 1, beside: side.left >= st.right - 1,
            labels: getComputedStyle(lab).display !== 'none', overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth} }""")
        if w < 1024:
            check(f"layers {w}: zone list below the picture, labels hidden, no sideways scroll",
                  ph["below"] and not ph["labels"] and ph["overflow"] <= 0, str(ph))
        else:
            check(f"layers {w}: labels on the picture, side panel {'beside' if w >= 1400 else 'below'} it, no sideways scroll",
                  ph["labels"] and (ph["beside"] if w >= 1400 else ph["below"]) and ph["overflow"] <= 0, str(ph))
        if w == 360:
            pg.locator(".zone-btn[data-zone=z4]").click()
            settle(pg, 200)
            t = pg.evaluate("document.querySelector('#lr-detail .zd-title') && document.querySelector('#lr-detail .zd-title').textContent")
            check("layers 360: tapping a zone in the list opens it", t == "Salitila ja räkit", str(t))
            run.shot(pg, "l2_layers_360.png", full_page=True)
        ctx.close()

    # The AI Oy table: no bar row; the legend keeps the risk colours.
    ctx = b.new_context(viewport={"width": 1680, "height": 1050})
    pg = ctx.new_page()
    pw_guard.load(pg, hub)
    pw_guard.settled(pg)
    mt = pg.evaluate("""() => ({labels: [...document.querySelectorAll('.matrix-labels .mlabel')].map(e => e.textContent),
        segs: document.querySelectorAll('.segments').length,
        legend: [document.querySelector('.legend-title').textContent, [...document.querySelectorAll('.legend-item')].map(e => e.textContent)]})""")
    check("table: the KERROKSET bar row is gone (the section above shows the layers)",
          "KERROKSET" not in mt["labels"] and mt["segs"] == 0 and len(mt["labels"]) == 12, str(mt["labels"]))
    check("table: the legend names the risk boxes' two colours",
          mt["legend"] == ["VÄRIT:", ["AI Oy", "Vastapuoli: pilvi- tai colocation-yhtiö"]], str(mt["legend"]))
    col = pg.evaluate("""() => { const bg = s => getComputedStyle(document.querySelector(s)).backgroundColor;
        return {ownBox: bg('.risk-box.fill-own'), cpBox: bg('.risk-box.fill-blue'), ownKey: bg('.legend .swatch.fill-own'),
                cpKey: bg('.legend .swatch.fill-blue'), ownCell: bg('.stairs-table td.own'), cpCell: bg('.stairs-table td.cp'),
                ownBtn: bg('.zone-btn.is-own'), cpBtn: bg('.zone-btn.is-cp')} }""")
    check("table: one colour convention on the hub (R62): the company navy, the counterparty light blue, in the section and the table",
          len({col["ownBox"], col["ownKey"], col["ownCell"], col["ownBtn"]}) == 1 and col["ownBox"] == "rgb(18, 34, 46)"
          and len({col["cpBox"], col["cpKey"], col["cpCell"], col["cpBtn"]}) == 1 and col["cpBox"] == "rgb(232, 239, 245)", str(col))
    ctx.close()

    # Naming rule, site-wide (R61): no "tarjoaja" as a role name anywhere in the explainer.
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    found = {}
    for slug in ["index"] + CARDS + PAGES:
        pw_guard.load(pg, run.base + slug + ".html")
        pw_guard.settled(pg)
        n = pg.evaluate("() => (document.body.innerText.match(/tarjoaj/gi) || []).length + Object.values(window.BM_GLOSSARY || {}).filter(e => /tarjoaj/i.test(e.definition)).length")
        if n:
            found[slug] = n
    check("naming: no 'tarjoaja' on any explainer page or in the glossary", not found, str(found))
    ctx.close()


SUITES = {"hub": suite_hub, "cards": suite_cards, "pages": suite_pages, "layers": suite_layers}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://127.0.0.1:8765/business-models/")
    ap.add_argument("--suite", nargs="*", choices=list(SUITES), default=list(SUITES))
    ap.add_argument("--shots", metavar="DIR", help="also save the review screenshots here (e.g. Output/screenshots/business-models)")
    args = ap.parse_args()
    pw_guard.keep_awake()
    run = Run(args.base, args.shots)
    summary = []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            for name in args.suite:
                print(f"== {name}")
                start = len(results)
                failed = pw_guard.run_suite(name, SUITES[name], b, run)
                if failed:                       # a timed-out or aborted suite counts as a failed check
                    results.append((failed, False))
                mine = results[start:]
                summary.append((name, sum(ok for _, ok in mine), len(mine)))
            b.close()
    finally:                                     # the summary prints even if the run itself breaks (R80)
        print()
        for name, ok, n in summary:
            print(f"{'OK  ' if ok == n else 'FAIL'} {name:6} {ok}/{n} checks passed")
        print(f"     {pw_guard.summary()}")
    return 0 if summary and len(summary) == len(args.suite) and all(ok == n for _, ok, n in summary) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())

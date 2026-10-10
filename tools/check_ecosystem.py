"""Checks for the ecosystem page (ecosystem.html): the poster's clickable boxes and
the selected-stakeholder card beside it, the walkthroughs, the case card, deep
links, the Relationship explorer, and the phone fallback.

The page's earlier phases were verified with one-off scripts that weren't kept,
the same failure mode as the explainer's interaction tests before they moved
into tools/ (PLAN.md ledger R9). This keeps the ecosystem checks in the repo.

The check that matters most here: after clicking any box on the poster, the
card's heading must be on screen. Before R20 (2026-10-09) the card was pinned
to the poster's top, so after a click lower on the poster its heading sat
above the screen at every width tested.

Needs Playwright (Chromium) and the site served locally, e.g. from the repo root:
    python -m http.server 8765 --bind 127.0.0.1
    python tools/check_ecosystem.py
    python tools/check_ecosystem.py --shots Output/screenshots/ecosystem
    python tools/check_ecosystem.py --base https://miikawir-ops.github.io/RayDar-DataCenter/

Exit code 0 when every check passes, 1 otherwise.
"""
import argparse
import os
import sys
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

# Desktop and laptop windows, including short ones (high display scaling).
DESKTOP = ((1680, 1050), (1440, 900), (1280, 800), (1280, 720), (1152, 720), (1024, 640))
PHONES = ((390, 844), (360, 740))
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def open_page(b, run, w, h, mobile=False, hash_=""):
    log, reqs = [], []
    ctx = b.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile)
    pg = ctx.new_page()
    pg.on("console", lambda m: log.append(m.text) if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: log.append(str(e)))
    pg.on("request", lambda r: reqs.append(r.url))
    pg.goto(run["base"] + "ecosystem.html" + hash_)
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(150)
    return ctx, pg, log, reqs


def sideways(pg):
    return pg.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")


CARD = """() => { const c = document.getElementById('compact-card'), n = c.querySelector('.sc-name, .sc-heading');
  const r = n.getBoundingClientRect(), cr = c.getBoundingClientRect();
  return {text: n.textContent.trim(), top: r.top, bottom: r.bottom, cardH: cr.height, vh: innerHeight} }"""
BELOW = """() => { const p = document.getElementById('panel-below'); const n = p.querySelector('.sc-name');
  return {shown: getComputedStyle(p).display !== 'none', name: n ? n.textContent.trim() : null} }"""
LABELS = """() => STAKEHOLDERS.filter(s => s.posterBox).map(s => [s.id,
  POSTER_GROUPS[s.id] ? POSTER_GROUPS[s.id].panelLabel : s.name])"""


def poster_desktop(b, run):
    for w, h in DESKTOP:
        ctx, pg, log, reqs = open_page(b, run, w, h)
        tag = f"{w}x{h}"
        check(f"{tag}: no console errors", not log, str(log))
        third = [u for u in reqs if not u.startswith(run["origin"]) and not u.startswith("data:")]
        check(f"{tag}: no third-party requests", not third, str(third))
        check(f"{tag}: no sideways scroll", sideways(pg) <= 0, f"{sideways(pg)}px")
        card = pg.evaluate(CARD)
        check(f"{tag}: card shows how-to by default", card["text"] == "How to use this map", card["text"])
        check(f"{tag}: card height at most half the window", card["cardH"] <= max(200, 0.5 * h) + 1, f"{card['cardH']:.0f}px")
        check(f"{tag}: no empty strip below the poster by default", not pg.evaluate(BELOW)["shown"])
        note = pg.evaluate("""() => { const n = document.querySelector('.poster-note');
            return n && {inCard: !!n.closest('.poster-card'), afterHint: n.previousElementSibling && n.previousElementSibling.classList.contains('img-hint'),
                         bg: getComputedStyle(n).backgroundColor, size: parseFloat(getComputedStyle(n).fontSize)} }""")
        check(f"{tag}: caveat is fine print under the poster, not a panel",
              note and note["inCard"] and note["afterHint"] and note["bg"] in ("rgba(0, 0, 0, 0)", "transparent") and note["size"] <= 11, str(note))
        hidden = []
        for sid, label in pg.evaluate(LABELS):
            pg.evaluate("(id) => document.getElementById('hotspot-' + id).scrollIntoView({block: 'center'})", sid)
            pg.wait_for_timeout(60)
            pg.locator("#hotspot-" + sid).click()
            pg.wait_for_timeout(420)
            c = pg.evaluate(CARD); below = pg.evaluate(BELOW)
            if not (c["text"] == label and c["top"] >= 0 and c["bottom"] <= c["vh"] and below["shown"] and below["name"] == label):
                hidden.append(f"{sid}: '{c['text']}' top {c['top']:.0f}, below {below}")
            pg.locator("#hotspot-" + sid).click()  # deselect
            pg.wait_for_timeout(250)
        check(f"{tag}: every box's click shows its name in the card on screen, and the details below", not hidden, "; ".join(hidden[:3]))
        check(f"{tag}: deselecting hides the details below again", not pg.evaluate(BELOW)["shown"])
        if w == 1680 and run["shots"]:
            pg.evaluate("window.scrollTo(0,0)")
            pg.screenshot(path=os.path.join(run["shots"], "eco_1680_full.png"), full_page=True)
        ctx.close()


# What each walkthrough step lights: on the poster by box (dso shares tso's
# box), in the explorer by stakeholder. Expected sets come from the page's own
# step data; this checks that the page renders them, not that they're right.
WT_EXPECTED = """(mode) => { const owner = id => { for (const o in POSTER_GROUPS) if (POSTER_GROUPS[o].extraIds.includes(id)) return o; return id; };
  const byId = Object.fromEntries(STAKEHOLDERS.map(s => [s.id, s]));
  return (mode === 'life' ? WALKTHROUGH_STEPS : MONEY_WALKTHROUGH_STEPS).map(s => ({title: s.title,
    poster: [...new Set(s.highlightIds.map(owner))].sort(), explorer: [...new Set(s.highlightIds)].sort(),
    pays: (s.payments || []).map(p => p.from + '>' + p.to).sort(),
    payText: (s.payments || []).map(p => byId[p.from].name + ' \u2192 ' + byId[p.to].name + ': ' + p.what)})) }"""
WT_STATE = """() => ({title: document.getElementById('wt-title').textContent,
  poster: [...document.querySelectorAll('.hotspot.glow')].map(e => e.id.replace('hotspot-', '')).sort(),
  mask: getComputedStyle(document.getElementById('poster-mask-svg')).display,
  cutouts: document.getElementById('poster-dim-mask').children.length - 1,
  heading: (document.querySelector('#compact-card .sc-heading') || {}).textContent || null,
  names: document.querySelectorAll('#compact-card .sc-name').length,
  explorer: STAKEHOLDERS.map(s => s.id).filter(id => document.getElementById('node-' + id).style.opacity === '1').sort(),
  pays: [...document.querySelectorAll('#money-svg .money-pay')].map(g => g.dataset.from + '>' + g.dataset.to).sort(),
  payText: [...document.querySelectorAll('#compact-card .sc-pay-list li')].map(li => li.textContent.trim())})"""


def walkthroughs(b, run):
    """Step through both paths in both views; every step must light exactly its stakeholders (R25).
    Choosing a path starts it at step 1 (R26); money steps draw one arrow per payer -> payee pair
    over the poster and list the same pairs in the card."""
    seen = {}
    for view in ("poster", "explorer"):
        ctx, pg, log, _ = open_page(b, run, 1680, 1050)
        if view == "explorer":
            pg.locator("#toggle-explorer").click(); pg.wait_for_timeout(200)
        for mode in ("life", "money"):
            steps, bad = pg.evaluate(WT_EXPECTED, mode), []
            pg.locator("#wt-mode-" + mode).click(); pg.wait_for_timeout(350)
            st = pg.evaluate(WT_STATE)
            check(f"{view}, {mode} path: choosing it lights step 1 at once",
                  st["title"] == steps[0]["title"] and st[view] == steps[0][view] and st[view], str(st))
            for i, exp in enumerate(steps):
                if i:
                    pg.locator("#wt-next").click(); pg.wait_for_timeout(350)
                st = pg.evaluate(WT_STATE)
                if view == "poster" and (st["pays"] != exp["pays"] or sorted(st["payText"]) != sorted(exp["payText"])):
                    bad.append(f"step {i + 1} money: arrows {st['pays']} vs {exp['pays']}; card {st['payText']}")
                if view == "poster":
                    ok = (st["title"] == exp["title"] and st["poster"] == exp["poster"] and st["mask"] == "block"
                          and st["cutouts"] == len(exp["poster"]) and st["names"] == len(exp["poster"])
                          and st["heading"] == ("Who pays whom" if exp["pays"] else "Currently highlighted"))
                else:
                    ok = st["title"] == exp["title"] and st["explorer"] == exp["explorer"]
                if not ok:
                    bad.append(f"step {i + 1}: {st}")
                seen.setdefault((view, mode), []).append(st[view])
            check(f"{view}, {mode} path: each of its {len(steps)} steps lights exactly its stakeholders", not bad, "; ".join(bad[:2]))
            for _ in steps:  # from the last step back past step 1 to the path's intro
                if pg.locator("#wt-prev").is_enabled():
                    pg.locator("#wt-prev").click(); pg.wait_for_timeout(120)
            st = pg.evaluate(WT_STATE)
            check(f"{view}, {mode} path: back at the intro nothing is lit and no money arrows",
                  not st["poster"] and st["mask"] == "none" and not st["pays"], str(st))
        check(f"{view} walkthroughs: no console errors", not log, str(log))
        ctx.close()
    life, money = seen[("poster", "life")], seen[("poster", "money")]
    check("the two paths light different sequences of boxes", life != money and all(life) and all(money), f"life {life} money {money}")
    only_money = [s for s in money if s not in life]
    check("Follow the money lights at least one set of boxes the life path never does", only_money, str(only_money))
    print(f"     note: {len(money) - len(only_money)} of {len(money)} money steps light exactly the same boxes as a life step")
    ctx, pg, log, _ = open_page(b, run, 1680, 1050)
    nopay = pg.evaluate("() => MONEY_WALKTHROUGH_STEPS.filter(s => !(s.payments || []).length).map(s => s.title)")
    # No euro badge may cover a printed poster label or a stakeholder box (R29), in any money step.
    covered = []
    pg.locator("#wt-mode-money").click(); pg.wait_for_timeout(300)
    for i in range(pg.evaluate("MONEY_WALKTHROUGH_STEPS.length")):
        if i:
            pg.locator("#wt-next").click(); pg.wait_for_timeout(300)
        covered += pg.evaluate("""(step) => { const W = 1536, H = 966, out = [];
            const rects = (typeof POSTER_LABELS === 'undefined' ? [] : POSTER_LABELS).map(l => [l.label, l])
              .concat(STAKEHOLDERS.filter(s => s.posterBox).map(s => [s.name, s.posterBox]));
            document.querySelectorAll('#money-svg .money-badge circle').forEach(c => {
              const x = +c.getAttribute('cx'), y = +c.getAttribute('cy'), r = +c.getAttribute('r') + 2;
              rects.forEach(([name, b]) => { const x0 = b.x * W / 100, y0 = b.y * H / 100, x1 = x0 + b.w * W / 100, y1 = y0 + b.h * H / 100;
                const nx = Math.max(x0, Math.min(x, x1)), ny = Math.max(y0, Math.min(y, y1));
                if ((x - nx) ** 2 + (y - ny) ** 2 < r * r) out.push('step ' + step + ': badge covers ' + name); }); });
            return out }""", i + 1)
    has_labels = pg.evaluate("() => typeof POSTER_LABELS !== 'undefined' && POSTER_LABELS.length")
    check("money badges cover no printed poster label and no stakeholder box", has_labels and not covered, f"labels {has_labels}; {covered[:4]}")
    pg.close(); ctx.close()
    ctx, pg, log, _ = open_page(b, run, 1680, 1050)
    pressed = pg.locator("#wt-mode-life").get_attribute("aria-pressed")
    pg.locator("#wt-mode-life").click(); pg.wait_for_timeout(350)
    st = pg.evaluate(WT_STATE)
    check("fresh load: clicking the already-active Life chip starts step 1",
          pressed == "true" and st["title"].startswith("1.") and st["poster"], f"pressed {pressed}, {st['title']}, lit {st['poster']}")
    check("every money step has payer -> payee pairs to draw", not nopay, str(nopay))
    pg.locator("#wt-mode-money").click(); pg.wait_for_timeout(350)
    pg.locator("#hotspot-capital").click(); pg.wait_for_timeout(350)
    left = pg.evaluate("() => document.querySelectorAll('#money-svg .money-pay').length")
    check("selecting a box during the money path clears the money arrows", left == 0, str(left))
    heat = pg.evaluate("() => RELATIONSHIPS.filter(r => r.label.startsWith('Waste heat')).map(r => r.from + '>' + r.to)")
    check("waste heat points the way the heat flows (operator -> district heating)", heat == ["operator>district_heating"], str(heat))
    lease = pg.evaluate("() => RELATIONSHIPS.filter(r => r.label.startsWith('Lease & services')).map(r => r.from + '>' + r.to)")
    check("leased capacity points the way it flows (operator -> hyperscaler)", lease == ["operator>hyperscaler"], str(lease))
    ctx.close()


def flows_desktop(b, run):
    ctx, pg, log, _ = open_page(b, run, 1680, 1050)
    pg.locator("#case-show").click(); pg.wait_for_timeout(900)
    st = pg.evaluate("() => ({glow: document.querySelectorAll('.hotspot.glow').length, top: document.getElementById('view-poster').getBoundingClientRect().top})")
    check("case card: highlights its boxes and scrolls the poster into view", st["glow"] >= 4 and abs(st["top"]) < 60, str(st))
    check("flows: no console errors", not log, str(log))
    ctx.close()

    ctx, pg, log, _ = open_page(b, run, 1680, 1050, hash_="#capital")
    c = pg.evaluate(CARD); below = pg.evaluate(BELOW)
    check("deep link #capital: card and details show Capital & Finance",
          c["text"] == "Capital & Finance" and below["shown"] and below["name"] == "Capital & Finance", f"{c['text']} {below}")
    ctx.close()


def explorer(b, run):
    for w, h in ((1680, 1050), (1280, 800)):
        ctx, pg, log, _ = open_page(b, run, w, h)
        tag = f"explorer {w}"
        pg.locator("#toggle-explorer").click(); pg.wait_for_timeout(300)
        vis = pg.evaluate("""() => ({explorer: getComputedStyle(document.getElementById('view-explorer')).display !== 'none',
            poster: getComputedStyle(document.getElementById('view-poster')).display !== 'none',
            below: getComputedStyle(document.getElementById('panel-below')).display !== 'none'})""")
        check(f"{tag}: toggle shows the explorer only", vis["explorer"] and not vis["poster"] and not vis["below"], str(vis))
        geo = pg.evaluate("""() => { const boxes = [...document.querySelectorAll('.node-box')].map(g => {
              const frame = g.querySelector('.node-bg') || g.querySelector('rect'), icon = g.querySelector('svg');
              const r = frame.getBoundingClientRect(), t = g.querySelector('text').getBoundingClientRect(),
                    i = icon ? icon.getBoundingClientRect() : {left: 1e9, top: 1e9, right: 1e9, bottom: 1e9};
              return {id: g.id, r: [r.left, r.top, r.right, r.bottom], t: [t.left, t.top, t.right, t.bottom], i: [i.left, i.top, i.right, i.bottom],
                      glow: g.style.getPropertyValue('--glow')}; });
            const over = [];
            for (let a = 0; a < boxes.length; a++) for (let c = a + 1; c < boxes.length; c++) {
              const A = boxes[a].r, C = boxes[c].r;
              if (Math.min(A[2], C[2]) - Math.max(A[0], C[0]) > 0.5 && Math.min(A[3], C[3]) - Math.max(A[1], C[1]) > 0.5) over.push(boxes[a].id + '/' + boxes[c].id); }
            const inside = (o, r) => o[0] >= r[0] - 0.5 && o[1] >= r[1] - 0.5 && o[2] <= r[2] + 0.5 && o[3] <= r[3] + 0.5;
            return {n: boxes.length, over, textOut: boxes.filter(x => !inside(x.t, x.r)).map(x => x.id),
                    iconOut: boxes.filter(x => !inside(x.i, x.r)).map(x => x.id), noGlow: boxes.filter(x => !x.glow).map(x => x.id),
                    edges: document.querySelectorAll('.edge-line').length, rels: RELATIONSHIPS.length,
                    edgeNoGlow: [...document.querySelectorAll('.edge-line')].filter(e => !e.style.getPropertyValue('--glow')).length} }""")
        check(f"{tag}: 15 boxes, none overlapping", geo["n"] == 15 and not geo["over"], str(geo["over"]))
        check(f"{tag}: every box's name and icon fit inside it", not geo["textOut"] and not geo["iconOut"], f"text {geo['textOut']} icon {geo['iconOut']}")
        check(f"{tag}: every box and arrow carries its glow colour", not geo["noGlow"] and geo["edges"] == geo["rels"] and geo["edgeNoGlow"] == 0, str(geo))
        pg.locator("#node-capital").click(); pg.wait_for_timeout(300)
        st = pg.evaluate("""() => ({title: document.querySelector('#side-panel .side-panel-title').textContent,
            sel: [...document.querySelectorAll('.node-box.is-selected')].map(g => g.id),
            op: Object.fromEntries([...document.querySelectorAll('.node-box')].map(g => [g.id.slice(5), g.style.opacity]))})""")
        check(f"{tag}: clicking a box selects it, fills the side panel, dims the unrelated",
              st["title"] == "Capital & Finance" and st["sel"] == ["node-capital"]
              and st["op"]["operator"] == "1" and st["op"]["construction"] == "1" and st["op"]["storage"] == "0.45", str(st))
        if run["shots"]:
            pg.locator("#view-explorer").screenshot(path=os.path.join(run["shots"], f"eco_explorer_{w}_capital.png"))
        empty = pg.evaluate("() => Object.entries(FLOW_TYPES).filter(([k]) => !RELATIONSHIPS.some(r => r.type === k)).map(([, f]) => f.label)")
        check(f"{tag}: every legend chip has arrows to filter (no control that does nothing)", not empty, str(empty))
        chip = pg.locator(".legend-chip", has_text="Capital / Financing")
        chip.click(); pg.wait_for_timeout(250)
        ops = pg.evaluate("""() => RELATIONSHIPS.map((r, i) => [r.type, document.getElementById('edge-' + i).style.opacity])""")
        check(f"{tag}: legend chip filters its arrows out", all(o == "0.06" for t, o in ops if t == "capital"), str(ops))
        chip.click(); pg.wait_for_timeout(250)
        pg.locator("#node-capital").click(); pg.wait_for_timeout(250)
        pg.locator("#node-hyperscaler").focus(); pg.keyboard.press("Enter"); pg.wait_for_timeout(250)
        title = pg.evaluate("() => document.querySelector('#side-panel .side-panel-title').textContent")
        check(f"{tag}: keyboard Enter selects a box", title == "Hyperscaler / Cloud", title)
        if run["shots"]:
            pg.locator("#node-hyperscaler").press("Enter"); pg.wait_for_timeout(250)
            pg.locator("#view-explorer").screenshot(path=os.path.join(run["shots"], f"eco_explorer_{w}_default.png"))
        check(f"{tag}: no console errors", not log, str(log))
        ctx.close()


def phones(b, run):
    for w, h in PHONES:
        ctx, pg, log, _ = open_page(b, run, w, h, mobile=True)
        tag = f"phone {w}"
        st = pg.evaluate("""() => { const vis = s => { const e = document.querySelector(s); return !!e && getComputedStyle(e).display !== 'none'; };
            return {toggle: vis('.view-toggle'), rail: vis('.compact-rail'), hotspot: vis('.hotspot'),
                    list: document.querySelectorAll('#mobile-list .mobile-item').length, listShown: vis('#mobile-list')} }""")
        check(f"{tag}: poster without hotspots or card, stakeholder list shown",
              not st["toggle"] and not st["rail"] and not st["hotspot"] and st["listShown"] and st["list"] == 15, str(st))
        check(f"{tag}: no sideways scroll", sideways(pg) <= 0, f"{sideways(pg)}px")
        check(f"{tag}: no console errors", not log, str(log))
        ctx.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://127.0.0.1:8765/")
    ap.add_argument("--shots", metavar="DIR", help="also save screenshots here")
    args = ap.parse_args()
    base = args.base if args.base.endswith("/") else args.base + "/"
    parts = urlsplit(base)
    run = {"base": base, "origin": f"{parts.scheme}://{parts.netloc}/", "shots": args.shots}
    if args.shots:
        os.makedirs(args.shots, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        for suite in (poster_desktop, walkthroughs, flows_desktop, explorer, phones):
            print(f"== {suite.__name__}")
            suite(b, run)
        b.close()
    fails = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())

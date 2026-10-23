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
import subprocess
import sys
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

import pw_guard

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
    pw_guard.load(pg, run["base"] + "ecosystem.html" + hash_)
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
    pays: [...new Set((s.payments || []).filter(p => owner(p.from) !== owner(p.to)).map(p => owner(p.from) + '>' + owner(p.to)))].sort(),
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
        n_sh = pg.evaluate("STAKEHOLDERS.length")
        check(f"{tag}: one box per stakeholder ({n_sh}), none overlapping", geo["n"] == n_sh and not geo["over"], str(geo["over"]))
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


NAV = """() => { const q = s => document.querySelector(s), cs = e => getComputedStyle(e);
  const btn = id => { const b = document.getElementById(id), r = b.getBoundingClientRect(),
      t = b.querySelector('.wt-mode-title') || b, d = b.querySelector('.wt-mode-desc');
    return {title: t === b ? b.textContent.trim() : t.textContent, desc: d ? d.textContent : null,
            icon: !!b.querySelector('.wt-mode-icon svg'), bg: cs(b).backgroundColor, pressed: b.getAttribute('aria-pressed'),
            w: r.width, titleSize: parseFloat(cs(t).fontSize), titleWeight: +cs(t).fontWeight}; };
  const start = q('#wt-start'), wt = q('.walkthrough'), tab = q('#toggle-poster');
  const toRgb = hex => { const n = parseInt(hex.slice(1), 16); return 'rgb(' + [n >> 16 & 255, n >> 8 & 255, n & 255].join(', ') + ')'; };
  const lum = c => { const m = (c.match(/[\d.]+/g) || [0, 0, 0]).map(Number);
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(m[0]) + 0.7152 * f(m[1]) + 0.0722 * f(m[2]); };
  const icon = id => { const i = document.querySelector('#' + id + ' .wt-mode-icon');
    return i && {text: i.textContent.trim(), circles: i.querySelectorAll('circle').length, bg: cs(i).backgroundColor}; };
  const colours = el => [el, ...el.querySelectorAll('*')].flatMap(e => [cs(e).color, cs(e).backgroundColor, cs(e).borderTopColor]);
  const live = q('.family-link.fl-live'), ed = q('.family-link.fl-editorial'), marker = q('.fl-live-marker');
  return {life: btn('wt-mode-life'), money: btn('wt-mode-money'), capital: toRgb(FLOW_TYPES.capital.color),
          lifeIcon: icon('wt-mode-life'), moneyIcon: icon('wt-mode-money'),
          moneyLum: lum(cs(q('#wt-mode-money')).backgroundColor), moneyBorder: cs(q('#wt-mode-money')).borderTopColor,
          heroTitle: parseFloat(cs(q('.hero-title-lg')).fontSize),
          live: live && {text: live.textContent, marker: marker && marker.textContent.trim(), markerAnim: marker && cs(marker).animationName,
                         markerDotAnim: marker && cs(marker, '::before').animationName},
          editorial: ed && {bg: cs(ed).backgroundColor, color: cs(ed).color},
          rust: [...document.querySelectorAll('.family-link')].some(a => colours(a).includes('rgb(154, 71, 18)')),
          cardH: [...document.querySelectorAll('.family-link')].map(a => a.getBoundingClientRect().height),
          posterTop: q('#poster-img').getBoundingClientRect().top, vh: innerHeight,
          start: start && {text: start.textContent.trim(), shown: cs(start).display !== 'none', anim: cs(start).animationName},
          wtInner: wt.clientWidth - parseFloat(cs(wt).paddingLeft) - parseFloat(cs(wt).paddingRight),
          tab: {size: parseFloat(cs(tab).fontSize), weight: +cs(tab).fontWeight, bg: cs(tab).backgroundImage, shadow: cs(tab).boxShadow,
                shown: cs(q('.view-toggle')).display !== 'none'},
          cards: [...document.querySelectorAll('.family-link')].map(a => ({href: a.getAttribute('href'),
            open: (a.querySelector('.fl-open') || {}).textContent || null,
            openShown: !!a.querySelector('.fl-open') && a.querySelector('.fl-open').getBoundingClientRect().width > 0,
            fi: [...a.querySelectorAll('.fl-tag')].map(t => t.textContent),
            tile: a.querySelector('.fl-icon') ? cs(a.querySelector('.fl-icon')).backgroundColor : null, arrow: !!a.querySelector('.fl-arrow')})),
          looping: document.getAnimations().filter(an => an.effect && an.effect.getTiming().iterations === Infinity).length} }"""


def navigation(b, run):
    """R50: the walkthrough buttons, the "Start here" label, the link cards and the view tabs."""
    for w, h, mobile in ((1680, 1050, False), (1280, 800, False), (390, 844, True), (360, 740, True)):
        ctx, pg, log, _ = open_page(b, run, w, h, mobile=mobile)
        tag = f"nav {w}"
        st = pg.evaluate(NAV)
        life, money = st["life"], st["money"]
        check(f"{tag}: walkthrough buttons carry an icon, a title and a one-line description",
              (life["title"], life["desc"], money["title"], money["desc"]) ==
              ("Life of a data center", "From permits to waste heat, step by step", "Follow the money", "Who pays whom"), str((life, money)))
        check(f"{tag}: walkthrough icons are the paths' own: a timeline for life, a euro sign for money (R51)",
              st["lifeIcon"] and st["lifeIcon"]["circles"] == 3 and st["moneyIcon"] and st["moneyIcon"]["text"] == "€",
              str((st["lifeIcon"], st["moneyIcon"])))
        check(f"{tag}: a static 'Start here' label above them",
              st["start"] and st["start"]["text"].lower() == "start here" and st["start"]["shown"] and st["start"]["anim"] == "none", str(st["start"]))
        cards = st["cards"]
        check(f"{tag}: each link card shows an 'Open →' pill instead of the small arrow",
              len(cards) == 2 and all(c["open"] == "Open →" and c["openShown"] and not c["arrow"] for c in cards), str(cards))
        check(f"{tag}: only the Finnish explainer card carries the FI tag",
              [c["fi"] for c in cards] == [[], ["FI"]] and cards[1]["href"] == "business-models/", str(cards))
        check(f"{tag}: each link card has a coloured icon tile",
              all(c["tile"] not in ("rgba(0, 0, 0, 0)", "transparent") for c in cards), str([c["tile"] for c in cards]))
        lv = st["live"]
        check(f"{tag}: Daily signals card: live-data style, a static LIVE marker, 'Updated every weekday'",
              lv and lv["marker"] == "LIVE" and lv["markerAnim"] == "none" and lv["markerDotAnim"] == "none"
              and "Updated every weekday" in lv["text"], str(lv))
        check(f"{tag}: explainer card in its editorial cream and navy, and no rust on either card",
              st["editorial"] == {"bg": "rgb(243, 241, 235)", "color": "rgb(18, 34, 46)"} and not st["rust"], str((st["editorial"], st["rust"])))
        if mobile:
            check(f"{tag}: walkthrough buttons span the walkthrough's width",
                  life["w"] >= st["wtInner"] - 2 and money["w"] >= st["wtInner"] - 2, f"{life['w']:.0f}/{money['w']:.0f} of {st['wtInner']:.0f}")
        else:
            check(f"{tag}: link cards are compact (at most 56px tall)", all(hh <= 56 for hh in st["cardH"]), str(st["cardH"]))
            check(f"{tag}: the page title is the largest text at the top, then the tabs, then the walkthrough titles",
                  st["heroTitle"] > st["tab"]["size"] > life["titleSize"], f"{st['heroTitle']} / {st['tab']['size']} / {life['titleSize']}")
            check(f"{tag}: tabs at normal size (16-17px, semi-bold) with a filled active tab",
                  st["tab"]["shown"] and 16 <= st["tab"]["size"] <= 17 and 600 <= st["tab"]["weight"] < 700
                  and "gradient" in st["tab"]["bg"], str(st["tab"]))
            top0 = pg.locator(".family-link").first.bounding_box()["y"]
            pg.locator(".family-link").first.hover(); pg.wait_for_timeout(300)
            top1 = pg.locator(".family-link").first.bounding_box()["y"]
            check(f"{tag}: a link card lifts on hover", top1 < top0 - 1, f"{top0:.1f} -> {top1:.1f}")
            pg.mouse.move(2, 2)
        pg.locator("#wt-mode-money").click(); pg.wait_for_timeout(350)
        st = pg.evaluate(NAV)
        check(f"{tag}: the active money button is a capital-yellow tint with a yellow outline and euro tile (the arrows' colour)",
              st["money"]["pressed"] == "true" and st["moneyBorder"] == st["capital"] and (st["moneyIcon"] or {}).get("bg") == st["capital"]
              and st["money"]["bg"] != st["capital"] and st["life"]["pressed"] == "false", str((st["money"], st["moneyBorder"], st["moneyIcon"], st["capital"])))
        check(f"{tag}: ...and toned down so it can't outshine the tabs (a tint, not a full yellow block)",
              st["moneyLum"] <= 0.25, f"luminance {st['moneyLum']:.3f}")
        pg.locator("#wt-mode-life").click(); pg.wait_for_timeout(350)
        st = pg.evaluate(NAV)
        check(f"{tag}: the active life button is filled with a family-purple tint",
              st["life"]["pressed"] == "true" and st["life"]["bg"] not in ("rgba(0, 0, 0, 0)", "transparent")
              and st["life"]["bg"].startswith("rgba(91, 79, 208"), str(st["life"]))
        check(f"{tag}: no continuous animation anywhere on the page", st["looping"] == 0, str(st["looping"]))
        check(f"{tag}: no sideways scroll", sideways(pg) <= 0, f"{sideways(pg)}px")
        check(f"{tag}: no console errors", not log, str(log))
        ctx.close()


EDGE = """() => { const vw = document.documentElement.clientWidth, out = {vw, scroll: document.documentElement.scrollWidth - vw, items: {}};
  const els = {reviewed: document.querySelector('.reviewed-note'), next: document.getElementById('wt-next'),
               ...Object.fromEntries([...document.querySelectorAll('.fl-open')].map((e, i) => ['open ' + (i + 1), e]))};
  for (const [k, e] of Object.entries(els)) { const r = e.getBoundingClientRect();
    out.items[k] = {gap: Math.round(vw - r.right), clipped: e.scrollWidth > e.clientWidth + 1}; }
  out.posterTop = Math.round(document.getElementById('poster-img').getBoundingClientRect().top);
  return out }"""


def right_edge(p, run):
    """R51: nothing clipped or scrolling sideways at the right edge, with real scrollbars; the poster's top
    is in the first screen at 1680x1050 and 1280x800."""
    b = p.chromium.launch(ignore_default_args=["--hide-scrollbars"])
    for w, h in ((1280, 800), (1440, 900), (1680, 1050), (1920, 1080)):
        ctx = b.new_context(viewport={"width": w, "height": h})
        pg = ctx.new_page(); pw_guard.load(pg, run["base"] + "ecosystem.html"); pg.wait_for_timeout(150)
        st = pg.evaluate(EDGE)
        bad = {k: v for k, v in st["items"].items() if v["gap"] < 0 or v["clipped"]}
        check(f"edge {w}: no sideways scroll, and 'Content reviewed', the Open pills and Next sit inside the right edge",
              st["scroll"] <= 0 and not bad, str(st))
        if (w, h) in ((1680, 1050), (1280, 800)):
            check(f"edge {w}x{h}: the top of the poster is in the first screen (starts at {st['posterTop']}px)",
                  st["posterTop"] <= h - 200, f"{st['posterTop']}px of {h}")
        ctx.close()
    b.close()


def content_r53(b, run):
    """R52/R53: the public-sector step (8 since R76), the step 1 addition, the Daily signals link
    (step 4 since R76), examples on every card, the GPU cloud."""
    ctx, pg, log, _ = open_page(b, run, 1680, 1050)
    pg.locator("#wt-mode-money").click(); pg.wait_for_timeout(350)
    st1 = pg.evaluate("""() => ({desc: document.getElementById('wt-desc').textContent,
        pays: [...document.querySelectorAll('#compact-card .sc-pay-list li')].map(li => li.textContent)})""")
    check("money step 1: says a hyperscaler's own facility has no rent (Hamina)",
          "no rent" in st1["desc"] and "Hamina" in st1["desc"], st1["desc"])
    check("money step 1: lists the GPU cloud payments", sum("GPU Cloud" in t for t in st1["pays"]) == 2, str(st1["pays"]))
    pg.locator("#wt-next").click(); pg.wait_for_timeout(250); pg.locator("#wt-next").click(); pg.wait_for_timeout(250)
    no_link = pg.evaluate("document.getElementById('wt-link').hidden")
    pg.locator("#wt-next").click(); pg.wait_for_timeout(350)
    link = pg.evaluate("() => { const a = document.getElementById('wt-link'); return {hidden: a.hidden, href: a.getAttribute('href'), text: a.textContent} }")
    check("money step 4 (R76): links to the Daily signals page as the investment flow of steps 3 and 4; step 3 has no link",
          no_link and not link["hidden"] and link["href"] == "index.html"
          and link["text"] == "Steps 3 and 4 are the investment flow the Daily signals page tracks →", str(link))
    for _ in range(4):
        pg.locator("#wt-next").click(); pg.wait_for_timeout(250)
    pg.wait_for_timeout(200)
    st7 = pg.evaluate("""() => ({title: document.getElementById('wt-title').textContent,
        note: document.getElementById('wt-note').hidden ? null : document.getElementById('wt-note').textContent,
        lit: [...document.querySelectorAll('.hotspot.glow')].map(e => e.id.replace('hotspot-', '')).sort(),
        arrows: [...document.querySelectorAll('#money-svg .money-pay')].map(g => g.dataset.from + '>' + g.dataset.to),
        pays: [...document.querySelectorAll('#compact-card .sc-pay-list li')].length,
        sources: document.querySelectorAll('#compact-card .sc-sources a').length,
        linkHidden: document.getElementById('wt-link').hidden})""")
    check("money step 8: the public sector's share lights the municipality and the operator, one arrow, five payments (R76: land split)",
          st7["title"] == "8. The public sector's share" and st7["lit"] == ["operator", "public_sector"]
          and st7["arrows"] == ["operator>public_sector"] and st7["pays"] == 5, str(st7))
    check("money step 8: the dated Finland line (energy tax 2.24 c/kWh from 1 July 2026, scheme dropped)",
          st7["note"] and "2.24 c/kWh" in st7["note"] and "1 July 2026" in st7["note"] and "dropped" in st7["note"]
          and "Reviewed 10/2026" in st7["note"], str(st7["note"]))
    check("money step 8: the card lists its sources", st7["sources"] >= 8, str(st7["sources"]))
    check("money step 8: no stray link from step 4", st7["linkHidden"])
    pg.locator("#wt-prev").click(); pg.wait_for_timeout(300)
    check("the step note disappears on a step without one", pg.evaluate("document.getElementById('wt-note').hidden"))

    data = pg.evaluate("""() => ({missing: STAKEHOLDERS.filter(s => !EXAMPLES[s.id]).map(s => s.id),
        empty: Object.entries(EXAMPLES).filter(([, e]) => !((e.global || []).length || (e.dashboard || []).length || (e.finland || []).length)).map(([k]) => k),
        unsourced: Object.entries(EXAMPLES).filter(([, e]) => ((e.global || []).length || (e.finland || []).length) && !(e.sources || []).length).map(([k]) => k),
        dashboard: Object.fromEntries(Object.entries(EXAMPLES).filter(([, e]) => e.dashboard).map(([k, e]) => [k, e.dashboard]))})""")
    check("examples: every stakeholder has them, each typed example has sources",
          not data["missing"] and not data["empty"] and not data["unsourced"], str(data))
    check("examples: operator, cooling, network and equipment take their companies from the dashboard's sub-layers",
          data["dashboard"] == {"operator": ["colocation"], "cooling": ["cooling"], "network": ["networking", "optical"], "equipment": ["compute"]},
          str(data["dashboard"]))
    # R59 item 5: the companies come from config.py through dashboard-companies.js, each sub-layer linking
    # to its card on the dashboard. The file must match config (the generator's --check).
    gen = subprocess.run([sys.executable, os.path.join(REPO, "tools", "gen_dashboard_companies.py"), "--check"],
                         capture_output=True, text=True)
    check("examples: dashboard-companies.js matches config.py (generated, not typed by hand)",
          gen.returncode == 0, (gen.stdout + gen.stderr).strip())
    subs = pg.evaluate("() => typeof DASHBOARD_SUBLAYERS === 'undefined' ? null : DASHBOARD_SUBLAYERS")
    check("examples: the page loads the dashboard's sub-layers and company names", bool(subs), str(subs))
    subs = subs or {}
    bad = []
    for sid in pg.evaluate("() => STAKEHOLDERS.filter(s => s.posterBox).map(s => s.id)"):
        pg.evaluate("(id) => document.getElementById('hotspot-' + id).scrollIntoView({block: 'center'})", sid)
        pg.locator("#hotspot-" + sid).click(); pg.wait_for_timeout(420)
        c = pg.evaluate("""() => ({card: (document.getElementById('compact-card').textContent.match(/Reviewed 10\/2026/g) || []).length,
            panelSources: document.querySelectorAll('#panel-below .sc-sources a').length,
            dash: [...document.querySelectorAll('#compact-card a.sc-dash-link')].map(a => [a.getAttribute('href'), a.textContent])})""")
        exp_groups = pg.evaluate("(id) => 1 + ((POSTER_GROUPS[id] || {}).extraIds || []).length", sid)
        exp_dash = [[f"index.html#{subs[l]['anchor']}", ", ".join(subs[l]["companies"]) + " →"]
                    for l in data["dashboard"].get(sid, []) if l in subs]
        if c["card"] != exp_groups or c["dash"] != exp_dash:
            bad.append(f"{sid}: {c} (expected {exp_dash})")
        pg.locator("#hotspot-" + sid).click(); pg.wait_for_timeout(250)
    check("examples: every poster box's card shows its examples (each stakeholder in a shared box), dashboard links where due", not bad, "; ".join(bad[:3]))
    pg.locator("#hotspot-capital").click(); pg.wait_for_timeout(400)
    check("examples: the full panel lists the sources", pg.evaluate("document.querySelectorAll('#panel-below .sc-sources a').length") >= 4)
    pg.locator("#hotspot-hyperscaler").click(); pg.wait_for_timeout(400)
    grp = pg.evaluate("() => [...document.querySelectorAll('#compact-card .sc-subgroup-title')].map(e => e.textContent)")
    check("GPU cloud: shares the hyperscaler box on the poster, as its own section", grp == ["Hyperscaler / Cloud", "GPU Cloud (Neocloud)"], str(grp))
    rels = pg.evaluate("() => RELATIONSHIPS.filter(r => r.from === 'neocloud' || r.to === 'neocloud').map(r => r.from + '>' + r.to).sort()")
    check("GPU cloud: its five relationships", rels == sorted(["operator>neocloud", "equipment>neocloud", "capital>neocloud",
                                                             "neocloud>enterprise", "neocloud>hyperscaler"]), str(rels))
    check("content: no console errors", not log, str(log))
    ctx.close()
    ctx, pg, log, _ = open_page(b, run, 1680, 1050)
    pg.locator("#toggle-explorer").click(); pg.wait_for_timeout(300)
    pg.locator("#node-neocloud").click(); pg.wait_for_timeout(300)
    side = pg.evaluate("() => ({title: document.querySelector('#side-panel .side-panel-title').textContent, ex: document.querySelector('#side-panel .sc-examples') !== null})")
    check("GPU cloud: its own box in the explorer, with examples in the side panel", side == {"title": "GPU Cloud (Neocloud)", "ex": True}, str(side))
    ctx.close()


# R76: the phase of every payment, as Ray set them (2026-10-23): build in step 2, step 4, the
# operator's equipment, cooling and generator purchases in step 3 and the land price in step 8;
# operate everywhere else.
BUILD = {("operator", "construction", "construction contracts"), ("capital", "operator", "loans and equity"),
         ("capital", "construction", "development financing"), ("operator", "equipment", "power and electrical equipment"),
         ("operator", "cooling", "cooling systems"), ("operator", "backup_power", "generators and UPS systems"),
         ("hyperscaler", "equipment", "servers and GPUs"), ("neocloud", "equipment", "GPUs and servers"),
         ("enterprise", "equipment", "own servers, in colocation"), ("hyperscaler", "storage", "storage systems"),
         ("operator", "public_sector", "land price and building-permit fees")}
MONEY_STATE = """() => ({edges: [...document.querySelectorAll('.money-edge')].map(e => ({from: e.dataset.from, to: e.dataset.to,
    phase: e.dataset.phase, label: e.getAttribute('aria-label'), shown: e.style.display !== 'none', op: e.style.opacity,
    dash: getComputedStyle(e).strokeDasharray, width: getComputedStyle(e).strokeWidth})),
  relShown: [...document.querySelectorAll('.edge-line')].filter(e => e.style.display !== 'none').length,
  modes: ['ex-mode-rel', 'ex-mode-money'].map(id => document.getElementById(id).getAttribute('aria-pressed')),
  flowChips: !document.getElementById('legend').hidden, phaseChips: document.getElementById('phase-legend').hidden ? null
    : [...document.querySelectorAll('.phase-chip')].map(c => [c.textContent, c.getAttribute('aria-pressed')]),
  note: document.getElementById('phase-note').hidden ? null : document.getElementById('phase-note').textContent,
  labels: [...document.querySelectorAll('.edge-labels text')].map(t => t.textContent),
  overlap: (() => { const r = [...document.querySelectorAll('.edge-labels text')].map(t => t.getBBox()); let n = 0;
    for (let i = 0; i < r.length; i++) for (let j = i + 1; j < r.length; j++) { const a = r[i], c = r[j];
      if (a.x < c.x + c.width && c.x < a.x + a.width && a.y < c.y + c.height && c.y < a.y + a.height) n++; } return n })()})"""


# R77: no arrow may pass through a box other than its own two ends (a 4px margin), and no
# arrow label may sit on a box or off the map.
ROUTES = """() => { const out = [], nodes = STAKEHOLDERS.map(s => [s.id, document.querySelector('#node-' + s.id + ' .node-bg').getBBox()]);
  const arrows = [...RELATIONSHIPS.map((r, i) => [document.getElementById('edge-' + i), r.from, r.to]),
                  ...[...document.querySelectorAll('.money-edge')].map(e => [e, e.dataset.from, e.dataset.to])];
  arrows.forEach(([e, from, to]) => { const L = e.getTotalLength();
    for (let k = 1; k < 80; k++) { const p = e.getPointAtLength(L * k / 80);
      const hit = nodes.find(([id, b]) => id !== from && id !== to && p.x > b.x - 4 && p.x < b.x + b.width + 4 && p.y > b.y - 4 && p.y < b.y + b.height + 4);
      if (hit) { out.push(e.id + ' (' + from + '>' + to + ') x ' + hit[0]); break; } } });
  return {n: arrows.length, out} }"""
LABELS_CLEAR = """() => { const nodes = STAKEHOLDERS.map(s => document.querySelector('#node-' + s.id + ' .node-bg').getBBox());
  return [...document.querySelectorAll('.edge-labels text')].map(t => [t.textContent, t.getBBox()]).filter(([, r]) =>
    r.x < -20 || r.y < -20 || r.x + r.width > 1020 || r.y + r.height > 720
    || nodes.some(b => r.x < b.x + b.width && b.x < r.x + r.width && r.y < b.y + b.height && b.y < r.y + r.height)).map(([t]) => t) }"""


# R78: poster money arrows may not cross a stakeholder box other than their own two ends, nor a
# printed label pill. Any crossing fails unless it is listed here, by money step and arrow, with
# its reason; a listed crossing that no longer happens fails too, so the list can't go stale.
POSTER_CROSSINGS_ALLOWED = {
    (2, "capital>construction", "Equipment & Technology Suppliers"):
        "Equipment sits between the two boxes across their full width; the gap on its left is about 12px "
        "after margins and the card column closes the right, so no curve clears it without the poster "
        "image edit (R23).",
}
POSTER_CROSSINGS = """() => { const W = 1536, H = 966, out = [];
  document.querySelectorAll('#money-svg .money-pay').forEach(g => { const path = g.querySelector('path'), L = path.getTotalLength();
    const rects = STAKEHOLDERS.filter(s => s.posterBox && s.id !== g.dataset.from && s.id !== g.dataset.to).map(s => [s.name, s.posterBox])
      .concat(POSTER_LABELS.map(l => [l.label, l]));
    for (const [n, b] of rects) { const x0 = b.x * W / 100, y0 = b.y * H / 100, x1 = x0 + b.w * W / 100, y1 = y0 + b.h * H / 100;
      for (let k = 1; k < 80; k++) { const q = path.getPointAtLength(L * k / 80);
        if (q.x > x0 && q.x < x1 && q.y > y0 && q.y < y1) { out.push([g.dataset.from + '>' + g.dataset.to, n]); break; } } } });
  return out }"""


def money_flows(b, run):
    """R76: the money path's phases, the explorer's Money flows mode, labels on selection, the
    walkthrough in the explorer, and the phone list's payments."""
    ctx, pg, log, _ = open_page(b, run, 1680, 1050)
    pays = pg.evaluate("() => MONEY_WALKTHROUGH_STEPS.flatMap((s, i) => (s.payments || []).map(p => [i + 1, p.from, p.to, p.what, p.phase]))")
    titles = pg.evaluate("() => MONEY_WALKTHROUGH_STEPS.map(s => s.title)")
    check("money path: 8 steps, step 3 the facility's systems and step 4 the IT hardware (R76)",
          len(titles) == 8 and titles[2] == "3. The operator pays for the facility's systems" and titles[3] == "4. IT hardware: the biggest bill", str(titles))
    wrong = [p for p in pays if p[4] != ("build" if (p[1], p[2], p[3]) in BUILD else "operate")]
    check("every payment has its phase: build (one-off investment) or operate (recurring), as set in R76",
          not wrong and all(p[4] in ("build", "operate") for p in pays) and len({(p[1], p[2], p[3]) for p in pays if p[4] == "build"}) == len(BUILD),
          str(wrong[:4]))
    hw = [p for p in pays if p[0] in (3, 4) and p[2] in ("equipment", "storage")]
    check("the IT hardware is bought by whoever runs the IT layer, the operator only the facility's power and electrical equipment",
          sorted((p[1], p[3]) for p in hw) == sorted([("operator", "power and electrical equipment"), ("hyperscaler", "servers and GPUs"),
          ("neocloud", "GPUs and servers"), ("enterprise", "own servers, in colocation"), ("hyperscaler", "storage systems")]), str(hw))
    data = pg.evaluate("""() => ({eq: STAKEHOLDERS.find(s => s.id === 'equipment').description,
        rel: RELATIONSHIPS.filter(r => r.from === 'equipment' && r.to === 'hyperscaler').map(r => [r.type, r.label, !!r.added]),
        src: MONEY_WALKTHROUGH_STEPS[3].sources.map(s => s.url)})""")
    check("equipment: the description says who buys compute hardware; equipment -> hyperscaler added",
          data["eq"].endswith("the operator buys the facility's power and electrical equipment.")
          and data["rel"] == [["goods", "Servers, GPUs & network gear", True]], str(data))
    check("money step 4 cites Epoch AI's cost breakdown", data["src"] == ["https://epoch.ai/data-insights/ai-datacenter-cost-breakdown"], str(data["src"]))

    pg.locator("#toggle-explorer").click(); pg.wait_for_timeout(250)
    st = pg.evaluate(MONEY_STATE)
    check("explorer: the mode switch starts on Relationships, money arrows hidden",
          st["modes"] == ["true", "false"] and st["flowChips"] and st["phaseChips"] is None and st["note"] is None
          and not any(e["shown"] for e in st["edges"]) and st["relShown"] == pg.evaluate("RELATIONSHIPS.length"), str({k: st[k] for k in ("modes", "flowChips", "relShown")}))
    pg.locator("#ex-mode-money").click(); pg.wait_for_timeout(250)
    st = pg.evaluate(MONEY_STATE)
    edges = st["edges"]
    missing = [p for p in pays if not any(e["from"] == p[1] and e["to"] == p[2] and e["phase"] == p[4] and p[3] in e["label"] for e in edges)]
    check("Money flows: every payment of the money path is in the explorer's money view (payer -> payee, by phase)",
          not missing and all(e["shown"] for e in edges), str(missing[:4]))
    keys = [(e["from"], e["to"], e["phase"]) for e in edges]
    check("Money flows: one arrow per payer -> payee pair and phase", len(keys) == len(set(keys)) == len({(p[1], p[2], p[4]) for p in pays}), str(len(keys)))
    check("Money flows: phase chips All / Build / Operate replace the flow-type chips, with the legend line",
          st["modes"] == ["false", "true"] and not st["flowChips"] and st["relShown"] == 0
          and st["phaseChips"] == [["All", "true"], ["Build", "false"], ["Operate", "false"]]
          and st["note"] == "Build = one-off investment · Operate = recurring payments", str({k: st[k] for k in ("phaseChips", "note")}))
    check("Money flows: build dashed, operate solid, one width throughout (no sourced amounts per flow)",
          all((e["dash"] != "none") == (e["phase"] == "build") for e in edges) and len({e["width"] for e in edges}) == 1,
          str({(e["phase"], e["dash"], e["width"]) for e in edges}))
    pg.locator(".phase-chip[data-phase=build]").click(); pg.wait_for_timeout(250)
    st = pg.evaluate(MONEY_STATE)
    check("Money flows: the Build chip fades the operate arrows out",
          all(e["op"] == ("1" if e["phase"] == "build" else "0.06") for e in st["edges"]), str({(e["phase"], e["op"]) for e in st["edges"]}))
    if run["shots"]:
        pg.locator("#view-explorer").screenshot(path=os.path.join(run["shots"], "eco_money_build_1680.png"))
    pg.locator(".phase-chip[data-phase=all]").click(); pg.wait_for_timeout(200)
    if run["shots"]:
        pg.locator("#view-explorer").screenshot(path=os.path.join(run["shots"], "eco_money_all_1680.png"))
    pg.locator("#node-operator").click(); pg.wait_for_timeout(300)
    st = pg.evaluate(MONEY_STATE)
    mine = [e for e in st["edges"] if "operator" in (e["from"], e["to"])]
    check("Money flows: selecting the operator labels its arrows and fades the rest, labels clear of each other",
          len(st["labels"]) == len(mine) and all(e["op"] == "1" for e in mine)
          and all(e["op"] == "0.15" for e in st["edges"] if e not in mine) and st["overlap"] == 0, f"{len(st['labels'])}/{len(mine)} overlap {st['overlap']}")
    if run["shots"]:
        pg.locator("#view-explorer").screenshot(path=os.path.join(run["shots"], "eco_money_operator_1680.png"))
    pair = pg.evaluate("""() => { const e = [...document.querySelectorAll('.money-edge')].find(e => e.dataset.from === 'operator' && e.dataset.to === 'public_sector' && e.dataset.phase === 'operate');
        return {label: [...document.querySelectorAll('.edge-labels text')].map(t => t.textContent).filter(t => t.startsWith('taxes')), tip: e.getAttribute('aria-label')} }""")
    check("Money flows: operator -> public sector (operate) is labelled 'taxes and land rent'; its tooltip lists all four payments (R77)",
          pair["label"] == ["taxes and land rent"] and all(w in pair["tip"] for w in ("land rent, where the municipality leases the plot",
          "property tax, every year", "electricity tax", "corporate income tax")), str(pair))
    panel = pg.evaluate("""() => { const p = document.getElementById('side-panel');
        return {first: [...p.children].slice(0, 2).map(e => e.className + ':' + e.textContent.slice(0, 12)),
                titles: [...p.querySelectorAll('.mobile-pay-title')].map(e => e.textContent), phases: [...p.querySelectorAll('.mobile-pay-phase')].map(e => e.textContent),
                rels: p.querySelectorAll('.side-rel').length, desc: !!p.querySelector('.side-pay-desc')} }""")
    check("Money flows: the side panel shows Pays / Is paid by first, by phase, then the description; no relationship cards (R77)",
          panel["first"][0].startswith("side-panel-title:Data Center") and panel["first"][1].startswith("mobile-pay-title:Pays")
          and panel["titles"] == ["Pays", "Is paid by"] and panel["phases"] == ["Build", "Operate", "Build", "Operate"]
          and panel["rels"] == 0 and panel["desc"], str(panel))
    pg.locator("#node-operator").click(); pg.wait_for_timeout(200)
    routes = pg.evaluate(ROUTES)
    check(f"explorer: none of the {routes['n']} arrows (both modes) passes through a box other than its own two ends (R77)",
          routes["n"] == pg.evaluate("RELATIONSHIPS.length") + len(edges) and not routes["out"], str(routes["out"][:4]))
    in_box = {}
    for mode in ("money", "rel"):
        pg.locator("#ex-mode-" + mode).click(); pg.wait_for_timeout(150)
        for sid in pg.evaluate("STAKEHOLDERS.map(s => s.id)"):
            pg.locator("#node-" + sid).click(); pg.wait_for_timeout(80)
            bad_l = pg.evaluate(LABELS_CLEAR)
            if bad_l:
                in_box[mode + ":" + sid] = bad_l
            pg.locator("#node-" + sid).click(); pg.wait_for_timeout(50)
    check("explorer: with any box selected, in either mode, every arrow label sits outside the boxes and on the map (R77)", not in_box, str(in_box))
    if run["shots"]:
        pg.locator("#ex-mode-money").click(); pg.wait_for_timeout(150)
        pg.locator("#node-hyperscaler").click(); pg.mouse.move(1, 1); pg.wait_for_timeout(350)
        pg.locator("#view-explorer").screenshot(path=os.path.join(run["shots"], "eco_money_hyperscaler_1680.png"))
        pg.locator("#node-hyperscaler").click(); pg.wait_for_timeout(200)
    storage = pg.evaluate("() => RELATIONSHIPS.find(r => r.from === 'storage' && r.to === 'operator').explanation")
    check("storage -> operator says storage is bought by whoever runs the IT layer (R77)",
          storage == "Storage suppliers provide the arrays and systems for data protection and backup; like servers, they are bought by whoever runs the IT layer.", storage)
    pg.locator("#ex-mode-rel").click(); pg.wait_for_timeout(200)
    pg.locator("#node-operator").click(); pg.wait_for_timeout(300)
    st = pg.evaluate(MONEY_STATE)
    n_rel = pg.evaluate("() => RELATIONSHIPS.filter(r => r.from === 'operator' || r.to === 'operator').length")
    check("Relationships: selecting a box labels its arrows too, clear of each other", len(st["labels"]) == n_rel and st["overlap"] == 0,
          f"{len(st['labels'])}/{n_rel} overlap {st['overlap']}")
    pg.locator("#node-operator").click(); pg.wait_for_timeout(200)
    # The money walkthrough in the explorer: choosing it shows the money arrows; each step's payments lit and labelled.
    pg.locator("#wt-mode-money").click(); pg.wait_for_timeout(300)
    bad = []
    for i in range(8):
        if i:
            pg.locator("#wt-next").click(); pg.wait_for_timeout(250)
        st = pg.evaluate(MONEY_STATE)
        step = [p for p in pays if p[0] == i + 1]
        lit = sorted({(e["from"], e["to"], e["phase"]) for e in st["edges"] if e["op"] == "1"})
        if st["modes"] != ["false", "true"] or lit != sorted({(p[1], p[2], p[4]) for p in step}) or st["overlap"]:
            bad.append(f"step {i + 1}: lit {lit}")
        if i == 3 and run["shots"]:
            pg.locator("#view-explorer").screenshot(path=os.path.join(run["shots"], "eco_money_step4_explorer_1680.png"))
    check("explorer: the money walkthrough switches to Money flows and lights each step's payments", not bad, "; ".join(bad[:2]))
    pg.locator("#wt-mode-life").click(); pg.wait_for_timeout(250)
    check("explorer: the life path switches back to Relationships", pg.evaluate(MONEY_STATE)["modes"] == ["true", "false"])
    check("money flows: no console errors", not log, str(log))
    ctx.close()

    # The poster at money step 4: its badges (one per pair of boxes) clear of labels and boxes (also checked for every step above).
    ctx, pg, log, _ = open_page(b, run, 1680, 1050)
    pg.locator("#wt-mode-money").click(); pg.wait_for_timeout(250)
    for _ in range(3):
        pg.locator("#wt-next").click(); pg.wait_for_timeout(250)
    arrows = pg.evaluate("() => [...document.querySelectorAll('#money-svg .money-pay')].map(g => g.dataset.from + '>' + g.dataset.to).sort()")
    check("poster, money step 4: arrows from the cloud box and the customers to equipment and storage",
          arrows == ["enterprise>equipment", "hyperscaler>equipment", "hyperscaler>storage"], str(arrows))
    pg.locator("#wt-mode-money").click(); pg.wait_for_timeout(300)      # back to money step 1
    found = set()
    for i in range(8):
        if i:
            pg.locator("#wt-next").click(); pg.wait_for_timeout(250)
        for arrow, what in pg.evaluate(POSTER_CROSSINGS):
            found.add((i + 1, arrow, what))
        if run["shots"] and i + 1 in (2, 5):
            pg.locator("#view-poster").screenshot(path=os.path.join(run["shots"], f"eco_poster_money_step{i + 1}_1680.png"))
    new = sorted(found - set(POSTER_CROSSINGS_ALLOWED)); stale = sorted(set(POSTER_CROSSINGS_ALLOWED) - found)
    check(f"poster: no money curve crosses another box or a printed pill, in any step, beyond the allowlist ({len(POSTER_CROSSINGS_ALLOWED)} listed) (R78)",
          not new and not stale, f"not allowed {new}; listed but no longer crossing {stale}")
    for key, why in POSTER_CROSSINGS_ALLOWED.items():
        print(f"     allowed: money step {key[0]}, {key[1]} crosses {key[2]}: {why}")
    if run["shots"]:
        pg.locator("#view-poster").screenshot(path=os.path.join(run["shots"], "eco_poster_money_step4_1680.png"))
    ctx.close()

    # Phones: the explorer is hidden, so the list shows each stakeholder's payments.
    ctx, pg, log, _ = open_page(b, run, 390, 844, mobile=True)
    m = pg.evaluate("""() => { const item = [...document.querySelectorAll('#mobile-list .mobile-item')].find(d => d.querySelector('summary').textContent === 'Data Center Operator');
        return {titles: [...item.querySelectorAll('.mobile-pay-title')].map(e => e.textContent), phases: [...item.querySelectorAll('.mobile-pay-phase')].map(e => e.textContent),
                items: item.querySelectorAll('.mobile-pay-list li').length} }""")
    check("phone: each stakeholder lists who it pays and who pays it, grouped by phase",
          m["titles"] == ["Pays", "Is paid by"] and m["phases"] == ["Build", "Operate", "Build", "Operate"] and m["items"] >= 15, str(m))
    check("phone money list: no console errors", not log, str(log))
    ctx.close()


def phones(b, run):
    for w, h in PHONES:
        ctx, pg, log, _ = open_page(b, run, w, h, mobile=True)
        tag = f"phone {w}"
        st = pg.evaluate("""() => { const vis = s => { const e = document.querySelector(s); return !!e && getComputedStyle(e).display !== 'none'; };
            return {toggle: vis('.view-toggle'), rail: vis('.compact-rail'), hotspot: vis('.hotspot'),
                    list: document.querySelectorAll('#mobile-list .mobile-item').length, listShown: vis('#mobile-list')} }""")
        check(f"{tag}: poster without hotspots or card, stakeholder list shown",
              not st["toggle"] and not st["rail"] and not st["hotspot"] and st["listShown"] and st["list"] == pg.evaluate("STAKEHOLDERS.length"), str(st))
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
    suites = (poster_desktop, walkthroughs, flows_desktop, explorer, navigation, content_r53, money_flows, phones)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            for suite in suites:
                print(f"== {suite.__name__}")
                failed = pw_guard.run_suite(suite.__name__, suite, b, run)
                if failed:                       # a timed-out or aborted suite counts as a failed check
                    results.append((failed, False))
            print("== right_edge")
            failed = pw_guard.run_suite("right_edge", right_edge, p, run)
            if failed:
                results.append((failed, False))
            b.close()
    finally:                                     # the summary prints even if the run itself breaks (R80)
        fails = [r for r in results if not r[1]]
        print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
        print(f"     {pw_guard.summary()}")
    return 1 if fails or not results else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())

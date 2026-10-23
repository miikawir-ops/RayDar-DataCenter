"""Sweep the business-models explainer pages across a continuous width range and
report layout breakage: content escaping its card or box, text overflowing its
box, the hub matrix's rows/legend coming apart, misaligned layer-cake spans,
the header nav not fitting, and sideways page scroll.

Fixed-breakpoint screenshots missed a hub bug that only appeared between them
(risk boxes overflowing their card below ~1366px), so this checks every width
in the range, not a handful.

Needs Playwright (Chromium) and the site served locally, e.g. from the repo root:
    python -m http.server 8765 --bind 127.0.0.1
    python tools/check_layout_sweep.py                       # all 11 pages, 1024-1680px, 8px steps
    python tools/check_layout_sweep.py --pages index --step 4
    python tools/check_layout_sweep.py --base https://miikawir-ops.github.io/RayDar-DataCenter/business-models/
    python tools/check_layout_sweep.py --shots Output/screenshots/phones   # also the R79 phone cases' screenshots

It also checks two phone layouts at 360 and 390px (R79): the dashboard's chain bar (one line, a
fade cue when it scrolls; skipped when the dashboard isn't generated locally) and the ecosystem
page's walkthrough (every step's text and both buttons on screen).

Exit code 0 when every page is clean at every width, 1 otherwise.
"""
import argparse
import os
import sys
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

import pw_guard

PAGES = ["index", "public-cloud", "gpu-cloud", "retail-colocation", "wholesale-colocation", "own-data-center",
         "value-chain", "financing", "specialised-models", "why-finland", "glossary"]
# Boxes whose content must stay inside them. Anything inside a sideways scroller
# (.scroll-x__inner) is exempt: scrolling there is intended.
BOXES = (".model,.panel,.layer,.role,.band-col,.asset,.example,.spec-card,.why-card,.glossary-card,.vc-box,"
         ".vc-note,.chip,.pill,.callout,.crow,.risk-item,.key-row,.flow,.term,.risk-box")
CHECK = """(BOXES) => {
  const issues = [], inScroller = e => !!e.closest('.scroll-x__inner');
  document.querySelectorAll(BOXES).forEach(bx => {
    if (inScroller(bx) || !bx.offsetParent) return;
    const r = bx.getBoundingClientRect();
    bx.querySelectorAll('*').forEach(d => {
      if (!d.offsetParent || d.closest('.cell-label') || inScroller(d)) return;  // scrolled content is clipped by its scroller
      const q = d.getBoundingClientRect(); if (!q.width) return;
      const o = Math.max(q.right - r.right, r.left - q.left);
      if (o > 0.5) issues.push(`escapes ${bx.className.split(' ')[0]}: "${(d.textContent || '').trim().slice(0, 28)}" (${o.toFixed(1)}px)`);
    });
    if (bx.scrollWidth > bx.clientWidth + 1) issues.push(`text overflows ${bx.className.split(' ')[0]}: "${bx.textContent.trim().slice(0, 28)}"`);
  });
  const spread = els => { const t = els.map(e => e.getBoundingClientRect().top); return Math.max(...t) - Math.min(...t); };
  const cols = [...document.querySelectorAll('.model')];
  if (cols.length && getComputedStyle(document.querySelector('.matrix')).display === 'grid') {  // hub, desktop layout
    const all = [document.querySelector('.matrix-labels'), ...cols];
    for (let i = 0; i < all[0].children.length; i++) {
      const s = spread((i < 2 ? cols : all).map(c => c.children[i]));  // rows 1-2: label column is empty there
      if (s > 0.5) issues.push(`matrix row ${i + 1} misaligned by ${s.toFixed(1)}px`);
    }
    if (new Set([...document.querySelectorAll('.legend-item')].map(e => Math.round(e.getBoundingClientRect().top))).size > 1)
      issues.push('legend keys split across lines');
    if (new Set(cols.map(c => getComputedStyle(c.querySelector('.risk')).flexDirection)).size > 1)
      issues.push('risk boxes stacked in some columns only');
  }
  document.querySelectorAll('.cake').forEach(cake => {
    const L = [...cake.querySelectorAll('.layer')].map(l => l.getBoundingClientRect()); let row = 0;
    cake.querySelectorAll('.role').forEach(rl => {
      const span = +((rl.className.match(/span-(\\d)/) || [0, 1])[1]);
      const q = rl.getBoundingClientRect();
      if (Math.abs(q.top - L[row].top) > 0.6 || Math.abs(q.bottom - L[row + span - 1].bottom) > 0.6) issues.push('layer cake span misaligned');
      row += span; if (row >= L.length) row = 0;
    });
  });
  const bar = document.querySelector('.bm-bar');
  if (bar) {
    const br = bar.getBoundingClientRect();
    const out = Math.max(0, ...[...bar.querySelectorAll('*')].filter(k => k.offsetParent).map(k => k.getBoundingClientRect().right - br.right));
    if (out > 0.5) issues.push(`header bar overflows by ${out.toFixed(1)}px`);
  }
  const hs = document.documentElement.scrollWidth - document.documentElement.clientWidth;
  if (hs > 0) issues.push(`page scrolls sideways by ${hs}px`);
  return [...new Set(issues)];
}"""


PHONES = ((360, 740), (390, 844))
STRIP = """() => { const s = document.getElementById('bottleneck-strip'), r = s.getBoundingClientRect(), cs = getComputedStyle(s);
  const tops = new Set([...s.children].map(c => Math.round(c.getBoundingClientRect().top)));
  return {rows: tops.size, h: Math.round(r.height), right: Math.round(r.right), vw: document.documentElement.clientWidth,
          over: s.scrollWidth > s.clientWidth + 1, cut: s.classList.contains('is-cut'), wrap: cs.flexWrap,
          sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth} }"""
WT = """() => { const w = document.querySelector('.walkthrough').getBoundingClientRect(), t = document.getElementById('wt-text');
  const p = document.getElementById('wt-prev').getBoundingClientRect(), n = document.getElementById('wt-next').getBoundingClientRect();
  const c = document.querySelector('.wt-controls').getBoundingClientRect();
  return {title: document.getElementById('wt-title').textContent, h: Math.round(w.height), vh: innerHeight,
          oneRow: Math.abs(p.top - n.top) < 2 && p.top > t.getBoundingClientRect().bottom - 1,
          inside: p.left >= w.left && n.right <= w.right + 0.5 && n.bottom <= w.bottom + 0.5,
          full: t.getBoundingClientRect().width >= c.width - 2, over: t.scrollHeight > t.clientHeight + 1,
          cut: t.classList.contains('is-cut'), len: t.textContent.length,
          sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth} }"""


def phone_cases(b, base, shots):
    """R79: the chain bar and the walkthrough at phone widths. Returns True when clean."""
    root = base.rsplit("business-models/", 1)[0]
    ok = True
    for w, h in PHONES:
        ctx = b.new_context(viewport={"width": w, "height": h}, is_mobile=True, has_touch=True)
        pg = ctx.new_page()
        # Dashboard chain bar: the page's own bar, then a long one (three trend words) that must scroll.
        resp = pw_guard.load(pg, urljoin(root, "index.html"))
        if not resp or resp.status != 200:
            print(f"SKIP chain bar {w}: no dashboard at {urljoin(root, 'index.html')} (generated in CI)")
        else:
            st = pg.evaluate(STRIP)
            if shots:
                pg.locator("#bottleneck-strip").scroll_into_view_if_needed()
                pg.screenshot(path=os.path.join(shots, f"chain_bar_{w}.png"), clip={"x": 0, "y": max(0, pg.locator("#bottleneck-strip").bounding_box()["y"] - 60), "width": w, "height": 160})
            pg.evaluate("""() => buildBottleneckStrip([
              {n1: 'Optical', score: 82, color: 'Red'}, {n1: 'Networking', score: 81, color: 'Red'},
              {n1: 'Cooling', score: 66, color: 'Orange'}, {n1: 'Colocation', score: 30, color: 'Blue'}], true)""")
            pg.wait_for_timeout(50)
            lg = pg.evaluate(STRIP)
            good = (st["rows"] == 1 and st["wrap"] == "nowrap" and st["right"] <= st["vw"] and st["cut"] == st["over"] and not st["sideways"]
                    and lg["rows"] == 1 and lg["over"] and lg["cut"] and lg["right"] <= lg["vw"] and not lg["sideways"])
            print(("OK   " if good else "FAIL ") + f"chain bar {w}: one line ({st['h']}px, cue {st['cut']} when cut {st['over']}); a long bar scrolls with the cue: {lg['over']}/{lg['cut']}")
            ok &= good
            pg.evaluate("() => { const s = document.getElementById('bottleneck-strip'); s.scrollLeft = s.scrollWidth; s.dispatchEvent(new Event('scroll')); }")
            pg.wait_for_timeout(50)
            end = pg.evaluate(STRIP)
            good = not end["cut"]
            print(("OK   " if good else "FAIL ") + f"chain bar {w}: the cue goes at the end of the scroll")
            ok &= good
        # Ecosystem walkthrough: every step of both paths.
        pw_guard.load(pg, urljoin(root, "ecosystem.html"))
        bad, longest = [], None
        for mode in ("life", "money"):
            pg.locator("#wt-mode-" + mode).click(); pg.wait_for_timeout(250)
            n = pg.evaluate(f"({'WALKTHROUGH_STEPS' if mode == 'life' else 'MONEY_WALKTHROUGH_STEPS'}).length")
            for i in range(n):
                if i:
                    pg.locator("#wt-next").click(); pg.wait_for_timeout(200)
                st = pg.evaluate(WT)
                if not (st["h"] <= st["vh"] and st["oneRow"] and st["inside"] and st["full"] and st["cut"] == st["over"] and not st["sideways"]):
                    bad.append(f"{st['title']}: {st}")
                if not longest or st["len"] > longest[1]:
                    longest = (mode, st["len"], i, st["title"])
        print(("OK   " if not bad else "FAIL ") + f"walkthrough {w}: every step fits the screen, text full width, Prev and Next on one row under it" + (f"; {bad[:2]}" if bad else ""))
        ok &= not bad
        if shots and longest:
            pg.locator("#wt-mode-" + longest[0]).click(); pg.wait_for_timeout(250)
            for _ in range(longest[2]):
                pg.locator("#wt-next").click(); pg.wait_for_timeout(200)
            pg.locator(".walkthrough").screenshot(path=os.path.join(shots, f"walkthrough_longest_{w}.png"))
            print(f"     longest step: {longest[3]} ({longest[1]} characters)")
        ctx.close()
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://127.0.0.1:8765/business-models/")
    ap.add_argument("--pages", nargs="*", default=PAGES)
    ap.add_argument("--min", type=int, default=1024)
    ap.add_argument("--max", type=int, default=1680)
    ap.add_argument("--step", type=int, default=8)
    ap.add_argument("--shots", help="folder for the R79 phone cases' screenshots")
    args = ap.parse_args()
    if args.shots:
        os.makedirs(args.shots, exist_ok=True)
    widths = sorted(set(range(args.min, args.max + 1, args.step)) | {args.max})
    failed, clean, done = False, 0, 0

    def sweep(b, slug):
        nonlocal failed, clean
        pg = b.new_page(viewport={"width": args.max, "height": 900})
        pw_guard.load(pg, args.base + slug + ".html")
        pg.evaluate("document.fonts.ready")
        bad = []
        for w in widths:
            pg.set_viewport_size({"width": w, "height": 900})
            pg.wait_for_timeout(30)
            issues = pg.evaluate(CHECK, BOXES)
            if issues:
                bad.append((w, issues))
        pg.close()
        if bad:
            failed = True
            print(f"FAIL {slug}: {len(bad)}/{len(widths)} widths, {bad[0][0]}-{bad[-1][0]}px; at {bad[0][0]}px: {bad[0][1][:4]}")
        else:
            clean += 1
            print(f"OK   {slug}: clean at all {len(widths)} widths ({args.min}-{args.max}px)")

    phones_ok = None

    def phones(b):
        nonlocal failed, phones_ok
        phones_ok = phone_cases(b, args.base, args.shots)
        if not phones_ok:
            failed = True

    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            for slug in args.pages:
                if pw_guard.run_suite("sweep " + slug, sweep, b, slug):
                    failed = True
                done += 1
            if pw_guard.run_suite("phones", phones, b):
                failed = True
            b.close()
    finally:                                     # the summary prints even if the run itself breaks (R80)
        phone_txt = "clean" if phones_ok else "not finished" if phones_ok is None else "failed"
        print(f"\nlayout sweep: {clean}/{len(args.pages)} pages clean, phone cases {phone_txt}; {pw_guard.summary()}")
    return 1 if failed or done < len(args.pages) or not phones_ok else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())

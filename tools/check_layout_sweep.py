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

Exit code 0 when every page is clean at every width, 1 otherwise.
"""
import argparse
import sys

from playwright.sync_api import sync_playwright

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


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://127.0.0.1:8765/business-models/")
    ap.add_argument("--pages", nargs="*", default=PAGES)
    ap.add_argument("--min", type=int, default=1024)
    ap.add_argument("--max", type=int, default=1680)
    ap.add_argument("--step", type=int, default=8)
    args = ap.parse_args()
    widths = sorted(set(range(args.min, args.max + 1, args.step)) | {args.max})
    failed = False
    with sync_playwright() as p:
        b = p.chromium.launch()
        for slug in args.pages:
            pg = b.new_page(viewport={"width": args.max, "height": 900})
            pg.goto(args.base + slug + ".html")
            pg.wait_for_load_state("networkidle")
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
                print(f"OK   {slug}: clean at all {len(widths)} widths ({args.min}-{args.max}px)")
        b.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())

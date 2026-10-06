// Inline glossary tooltips for the business-models pages.
//
// One floating tooltip, positioned against the viewport and kept inside it.
// This replaces the ecosystem page's per-term child tooltip for two reasons
// found in its code: a tooltip inside a horizontally scrolling container
// (the hub's swipe track) gets clipped, and a fixed-width tooltip anchored
// at the term's left edge can run past the right edge of a phone screen.
//
// Designed so the ecosystem page can switch to it later with no data change:
//   markup  <span class="gloss" data-g="key">term</span>   (same as ecosystem.html)
//   data    { key: { term, definition, alt? } }             (same as its GLOSSARY)
//
// Desktop: shows on hover or keyboard focus; a click pins it.
// Touch: a tap toggles it. Tapping elsewhere, Esc, scrolling or resizing closes it.
// Keyboard: the tooltip lives as long as focus does. It follows its term
// when the page scrolls (Tab scrolls an off-screen term into view, which
// must not close the tooltip it just opened) and closes when focus moves or
// the term leaves the screen.
window.BMGlossary = (function () {
  let dict = {};
  let tip = null;
  let current = null;  // the term whose tooltip is showing
  let mode = null;     // how it was opened: "hover" | "focus" | "pin" (click/tap)
  let hoverTimer = 0;
  let scrollRaf = 0;

  const termOf = (node) => (node && node.closest ? node.closest(".gloss[data-g]") : null);
  const pinned = () => mode === "pin";

  function show(el, how) {
    const g = dict[el.dataset.g];
    if (!g) return;
    if (current && current !== el) current.removeAttribute("aria-describedby");
    current = el;
    mode = how;
    tip.textContent = "";
    const term = document.createElement("span");
    term.className = "gloss-tip-term";
    term.textContent = g.term;
    tip.appendChild(term);
    if (g.alt) {
      const alt = document.createElement("span");
      alt.className = "gloss-tip-alt";
      alt.textContent = g.alt;
      tip.appendChild(alt);
    }
    const def = document.createElement("span");
    def.className = "gloss-tip-def";
    def.textContent = g.definition;
    tip.appendChild(def);
    tip.hidden = false;
    el.setAttribute("aria-describedby", tip.id);
    place(el);
  }

  function hide() {
    clearTimeout(hoverTimer);
    if (current) current.removeAttribute("aria-describedby");
    current = null;
    mode = null;
    if (tip) tip.hidden = true;
  }

  function onScroll() {
    if (!current) return;
    if (mode !== "focus") { hide(); return; }
    if (scrollRaf) return;
    scrollRaf = requestAnimationFrame(() => {
      scrollRaf = 0;
      if (!current) return;
      const r = current.getBoundingClientRect();
      const vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight;
      if (r.bottom < 0 || r.top > vh || r.right < 0 || r.left > vw) hide();
      else place(current);
    });
  }

  // Above the term when there is room, otherwise below; horizontally clamped
  // to the viewport. A term that wraps across lines anchors to its first line.
  function place(el) {
    const margin = 8, gap = 8;
    const vw = document.documentElement.clientWidth;
    const vh = document.documentElement.clientHeight;
    const r = el.getClientRects()[0] || el.getBoundingClientRect();
    tip.style.maxWidth = Math.min(320, vw - 2 * margin) + "px";
    tip.style.left = "0px";
    tip.style.top = "0px";
    const w = tip.offsetWidth, h = tip.offsetHeight;
    const left = Math.max(margin, Math.min(r.left, vw - w - margin));
    let top = r.top - h - gap;
    if (top < margin) top = Math.min(r.bottom + gap, vh - h - margin);
    tip.style.left = Math.round(left) + "px";
    tip.style.top = Math.round(top) + "px";
  }

  // Returns the data-g keys that have no entry, so callers and checks can
  // fail loudly instead of shipping a dead tooltip. Unknown terms are left
  // as plain text.
  function init(dictionary) {
    dict = dictionary || {};
    const missing = [];
    document.querySelectorAll(".gloss[data-g]").forEach((el) => {
      if (!dict[el.dataset.g]) {
        missing.push(el.dataset.g);
        el.classList.remove("gloss");
        return;
      }
      el.tabIndex = 0;
    });
    if (missing.length) console.warn("Glossary: no entry for", missing);

    tip = document.createElement("div");
    tip.id = "gloss-tip";
    tip.className = "gloss-tip";
    tip.setAttribute("role", "tooltip");
    tip.hidden = true;
    document.body.appendChild(tip);

    document.addEventListener("pointerover", (e) => {
      if (e.pointerType !== "mouse") return;
      const el = termOf(e.target);
      if (!el || el === current) return;
      clearTimeout(hoverTimer);
      // Re-checked when the delay ends: a click in the meantime has already
      // opened (and pinned) this term, which a late hover must not undo.
      hoverTimer = setTimeout(() => { if (el !== current) show(el, "hover"); }, 80);
    });
    document.addEventListener("pointerout", (e) => {
      if (e.pointerType !== "mouse") return;
      const el = termOf(e.target);
      if (!el || el.contains(e.relatedTarget)) return;
      clearTimeout(hoverTimer);
      if (el === current && mode === "hover") hide();
    });
    document.addEventListener("click", (e) => {
      const el = termOf(e.target);
      if (!el) return;
      clearTimeout(hoverTimer);
      if (el === current && pinned()) hide();
      else show(el, "pin");
    });
    document.addEventListener("focusin", (e) => {
      const el = termOf(e.target);
      if (el && el !== current) show(el, "focus");
    });
    document.addEventListener("focusout", (e) => {
      if (termOf(e.target) === current) hide();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && current) { hide(); return; }
      const el = termOf(e.target);
      if (el && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); el.click(); }
    });
    document.addEventListener("pointerdown", (e) => {
      if (current && !termOf(e.target)) hide();
    });
    // Capture phase: element scrolls (the swipe track) don't bubble.
    window.addEventListener("scroll", onScroll, { capture: true, passive: true });
    window.addEventListener("resize", () => { if (current) hide(); });
    return missing;
  }

  return { init };
})();

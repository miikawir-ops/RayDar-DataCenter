// Layered responsibility view on the hub (ledger R61; brief
// docs/briefs/layered-responsibility.md). Draws the SVG overlay on the frozen
// image from the coordinates in kerrokset-data.js and runs the model tabs, the
// zones, the two markers, the side panel and the staircase. All text comes
// from the page: zone names from the zone list, who handles what from the
// staircase table (the single source), other strings from #lr-strings, so
// tools/check_port_text.py sees every word.
(function () {
  const D = window.BM_LAYERS, root = document.getElementById("kerrokset");
  if (!D || !root) return;
  const NS = "http://www.w3.org/2000/svg";
  const svg = root.querySelector(".layers-svg");
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  const T = {};
  root.querySelector("#lr-strings").content.querySelectorAll("[data-key]").forEach((e) => { T[e.dataset.key] = e.textContent.trim(); });

  const tabs = Array.from(root.querySelectorAll(".layers-tab"));
  const panel = root.querySelector("#lr-panel");
  const detail = root.querySelector("#lr-detail");
  const cloudNote = root.querySelector("#lr-cloud-note");
  const zoneBtns = Array.from(root.querySelectorAll(".zone-btn"));
  const markerBtns = Array.from(root.querySelectorAll(".marker-btn"));
  const table = root.querySelector(".stairs-table");
  const heads = Array.from(table.querySelectorAll("thead th[data-model]"));
  const colOf = {};
  heads.forEach((th, i) => { colOf[th.dataset.model] = i; });

  // Text of a cell without its footnote marker, and the markers on their own.
  const clean = (node) => { const c = node.cloneNode(true); c.querySelectorAll(".fn").forEach((f) => f.remove()); return c.textContent.trim(); };
  const marks = (node) => Array.from(node.querySelectorAll(".fn")).map((f) => f.textContent.trim());
  const rows = {};
  table.querySelectorAll("tbody tr[data-row]").forEach((tr) => {
    const th = tr.querySelector("th");
    rows[tr.dataset.row] = { tr, zone: tr.dataset.zone, name: clean(th), fn: marks(th),
                             tds: Array.from(tr.querySelectorAll("td")) };
  });
  const cell = (r, m) => rows[r].tds[colOf[m]];
  const zoneName = {};
  zoneBtns.forEach((b) => { zoneName[b.dataset.zone] = b.querySelector(".zone-name").textContent.trim(); });
  const noteText = (n) => { const li = root.querySelector("#lr-fn" + n); return li ? li.textContent.trim() : ""; };

  let model = (tabs.find((t) => t.getAttribute("aria-selected") === "true") || tabs[0]).dataset.model;
  let selected = null;     // {zone: "z4"} or {marker: "heat"}

  function el(name, attrs, parent) {
    const e = document.createElementNS(NS, name);
    Object.keys(attrs || {}).forEach((k) => e.setAttribute(k, attrs[k]));
    if (parent) parent.appendChild(e);
    return e;
  }
  const pts = (a) => a.map((p) => p.join(",")).join(" ");

  // Who handles a zone in a model, from the staircase: the cells of the
  // zone's rows if they agree; otherwise "Itse" or the model's counterparty
  // (row 11, land and building) by the model's typical line.
  function status(z, m) {
    const texts = D.zones[z].rows.map((r) => clean(cell(r, m)));
    const uniq = Array.from(new Set(texts));
    let who = uniq.length === 1 ? uniq[0] : (D.models[m].own.indexOf(z) >= 0 ? T.own : clean(cell("11", m)));
    const cls = who === T.own ? "own" : /itse/i.test(who) ? "mixed" : "cp";
    return { who, cls };
  }

  // -- Build the overlay ---------------------------------------------------
  const defs = el("defs", {}, svg);
  const pat = el("pattern", { id: "lr-hatch", width: 14, height: 14, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
  el("rect", { width: 14, height: 14, fill: "rgba(255,255,255,.30)" }, pat);
  el("rect", { width: 5, height: 14, fill: "rgba(31,78,110,.32)" }, pat);

  const zoneEls = {};
  const gZones = el("g", { class: "lr-zones" }, svg);
  Object.keys(D.zones).forEach((z) => {
    const d = D.zones[z];
    const g = el("g", { class: "lr-zone", "data-zone": z, tabindex: "0", role: "button", "aria-pressed": "false" }, gZones);
    el("polygon", { class: "lr-zone-shape", points: pts(d.poly) }, g);
    const right = d.poly.reduce((a, p) => (p[0] > a[0] ? p : a));
    el("line", { class: "lr-leader", x1: right[0] + 6, y1: right[1], x2: d.label[0], y2: d.label[1] + 31 }, g);
    const lab = el("g", { class: "lr-label" }, g);
    const box = el("rect", { class: "lr-label-box", x: d.label[0], y: d.label[1], rx: 10, width: 300, height: 62 }, lab);
    const name = el("text", { class: "lr-label-name", x: d.label[0] + 14, y: d.label[1] + 27 }, lab);
    name.textContent = zoneName[z];
    const who = el("text", { class: "lr-label-who", x: d.label[0] + 14, y: d.label[1] + 52 }, lab);
    zoneEls[z] = { g, box, name, who };
  });

  const gLines = el("g", { class: "lr-lines" }, svg);
  const range = el("polygon", { class: "lr-range" }, gLines);
  const rangeEdge = el("polyline", { class: "lr-range-edge" }, gLines);
  const rangeLabel = el("text", { class: "lr-range-label", "text-anchor": "end" }, gLines);
  const lines = [0, 1].map(() => ({
    halo: el("polyline", { class: "lr-line-halo" }, gLines),
    line: el("polyline", { class: "lr-line" }, gLines),
    label: el("text", { class: "lr-line-label" }, gLines),
    cur: null, raf: 0, on: false,
  }));

  const markerEls = {};
  [["grid", D.grid], ["heat", D.heat]].forEach(([k, m]) => {
    const tpl = root.querySelector("#lr-" + k).content;
    const title = tpl.querySelector(".zd-title").textContent.trim();
    const g = el("g", { class: "lr-marker lr-marker--" + k, "data-marker": k, tabindex: "0", role: "button",
                        "aria-pressed": "false", "aria-label": title }, svg);
    if (m.poly) el("polygon", { class: "lr-heat-shape", points: pts(m.poly) }, g);
    el("circle", { class: "lr-marker-ring", cx: m.at[0], cy: m.at[1], r: 13 }, g);
    el("circle", { class: "lr-marker-dot", cx: m.at[0], cy: m.at[1], r: 5 }, g);
    const t = el("text", { class: "lr-marker-label", x: m.label[0], y: m.label[1] }, g);
    if (k === "grid") {
      // The brief's label, "Liittymispiste: verkkoyhtiön vastuu päättyy tähän.",
      // from the template's first sentence, in three short lines over the forest.
      const first = tpl.querySelector("p").textContent.trim().split(". ")[0] + ".";
      const [head, rest] = first.split(": ");
      t.textContent = head + ":";
      const words = rest.split(" "), half = Math.ceil(words.length / 2);
      [words.slice(0, half).join(" "), words.slice(half).join(" ")].forEach((line, i) => {
        el("text", { class: "lr-marker-sub", x: m.label[0], y: m.label[1] + 25 * (i + 1) }, g).textContent = line;
      });
      el("line", { class: "lr-leader", x1: m.label[0] + 90, y1: m.label[1] + 60, x2: m.at[0] - 10, y2: m.at[1] - 10 }, g);
    } else {
      t.textContent = title;
    }
    markerEls[k] = g;
  });

  // -- State -----------------------------------------------------------------
  function sizeLabels() {
    Object.keys(zoneEls).forEach((z) => {
      const ze = zoneEls[z];
      try {
        const w = Math.max(ze.name.getComputedTextLength(), ze.who.getComputedTextLength());
        if (w > 0) ze.box.setAttribute("width", Math.ceil(w + 28));
      } catch (e) { /* hidden on phones: no layout, nothing to size */ }
    });
  }

  function setPts(ln, p) {
    const s = pts(p);
    ln.halo.setAttribute("points", s);
    ln.line.setAttribute("points", s);
    ln.cur = p;
  }

  // The line slides to its new gap; with reduced motion it jumps.
  function moveLine(ln, target, animate) {
    cancelAnimationFrame(ln.raf);
    if (!ln.cur || !animate || reduce.matches) { setPts(ln, target); return; }
    const from = ln.cur, t0 = performance.now(), dur = 450;
    const step = (now) => {
      const k = Math.min(1, (now - t0) / dur);
      const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      setPts(ln, from.map((p, i) => [p[0] + (target[i][0] - p[0]) * e, p[1] + (target[i][1] - p[1]) * e]));
      if (k < 1) ln.raf = requestAnimationFrame(step); else setPts(ln, target);
    };
    ln.raf = requestAnimationFrame(step);
  }

  function update(animate) {
    const m = D.models[model];
    tabs.forEach((t) => {
      const on = t.dataset.model === model;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
    });
    panel.setAttribute("aria-labelledby", "lr-tab-" + model);
    Object.keys(zoneEls).forEach((z) => {
      const st = status(z, model), ze = zoneEls[z];
      ze.g.classList.remove("is-own", "is-mixed", "is-cp");
      ze.g.classList.add("is-" + st.cls);
      ze.who.textContent = st.who;
      ze.g.setAttribute("aria-label", zoneName[z] + ": " +
        (st.cls === "own" ? T.handlesOwn : st.cls === "cp" ? st.who + " " + T.handles : st.who));
      const btn = zoneBtns.find((b) => b.dataset.zone === z);
      btn.classList.remove("is-own", "is-mixed", "is-cp");
      btn.classList.add("is-" + st.cls);
      btn.querySelector(".zone-who").textContent = st.who;
    });
    sizeLabels();
    const lead = lines.find((l) => l.on && l.cur);
    lines.forEach((ln, i) => {
      const spec = m.lines[i];
      const show = !!spec;
      [ln.halo, ln.line, ln.label].forEach((e) => { e.style.display = show ? "" : "none"; });
      if (!show) { ln.on = false; return; }
      const target = D.gaps[spec[0]];
      if (!ln.on && lead && lead !== ln) ln.cur = lead.cur;     // a new line slides out of the existing one
      moveLine(ln, target, animate);
      ln.on = true;
      const end = target[target.length - 1];
      ln.label.setAttribute("x", end[0] + 16);
      ln.label.setAttribute("y", end[1] + 8);
      ln.label.textContent = T[spec[1]];
      ln.label.dataset.gap = spec[0];
    });
    if (m.range) {
      const up = D.gaps[m.range[0]], low = D.gaps[m.range[1]];
      range.setAttribute("points", pts(up.concat(low.slice().reverse())));
      rangeEdge.setAttribute("points", pts(up));
      rangeLabel.setAttribute("x", up[0][0] - 12);
      rangeLabel.setAttribute("y", up[0][1] + 7);
      rangeLabel.textContent = model === "public-cloud" ? T.rangePublic : T.rangeGpu;
      [range, rangeEdge, rangeLabel].forEach((e) => { e.style.display = ""; });
    } else {
      [range, rangeEdge, rangeLabel].forEach((e) => { e.style.display = "none"; });
    }
    cloudNote.hidden = !m.range;
    heads.forEach((th, i) => {
      table.querySelectorAll("tbody tr[data-row]").forEach((tr) => tr.children[i + 1].classList.toggle("is-col", th.dataset.model === model));
    });
    if (selected) render();
  }

  function render() {
    detail.textContent = "";
    if (selected && selected.marker) {
      detail.appendChild(root.querySelector("#lr-" + selected.marker).content.cloneNode(true));
      return;
    }
    const z = selected.zone, st = status(z, model);
    const h = document.createElement("h3");
    h.className = "zd-title";
    h.textContent = zoneName[z];
    const who = document.createElement("p");
    who.className = "zd-who" + (st.cls === "own" ? " is-own" : "");
    who.textContent = st.who;
    const ul = document.createElement("ul");
    ul.className = "zd-rows";
    const notes = [];
    D.zones[z].rows.forEach((r) => {
      const c = cell(r, model);
      const li = document.createElement("li");
      const a = document.createElement("span");
      a.textContent = rows[r].name;
      const b = document.createElement("span");
      b.className = "zd-cell";
      b.textContent = clean(c);
      li.append(a, b);
      ul.appendChild(li);
      rows[r].fn.concat(marks(c)).forEach((n) => { if (notes.indexOf(n) < 0) notes.push(n); });
    });
    // A model's own footnote (GPU cloud: whose data center it runs in) is about
    // the building, so it shows on the building zones only.
    if (D.zones[z].site && st.cls !== "own")
      marks(heads[colOf[model]]).forEach((n) => { if (notes.indexOf(n) < 0) notes.push(n); });
    detail.append(h, who, ul);
    notes.forEach((n) => {
      const p = document.createElement("p");
      p.className = "zd-note";
      p.textContent = noteText(n);
      detail.appendChild(p);
    });
    // Zone-specific text (Z5: redundancy, ledger R64), kept in a template like the markers'.
    const extra = root.querySelector("#lr-zone-" + z);
    if (extra) detail.appendChild(extra.content.cloneNode(true));
  }

  function select(sel) {
    selected = sel;
    Object.keys(zoneEls).forEach((z) => {
      const on = !!sel.zone && sel.zone === z;
      zoneEls[z].g.classList.toggle("is-selected", on);
      zoneEls[z].g.setAttribute("aria-pressed", on ? "true" : "false");
    });
    zoneBtns.forEach((b) => b.setAttribute("aria-pressed", sel.zone === b.dataset.zone ? "true" : "false"));
    Object.keys(markerEls).forEach((k) => {
      const on = sel.marker === k;
      markerEls[k].classList.toggle("is-selected", on);
      markerEls[k].setAttribute("aria-pressed", on ? "true" : "false");
    });
    markerBtns.forEach((b) => b.setAttribute("aria-pressed", sel.marker === b.dataset.marker ? "true" : "false"));
    render();
  }

  function choose(m) {
    if (m === model) return;
    model = m;
    update(true);
  }

  // A zone and its staircase rows light up together (hover or focus).
  function hot(z, on) {
    if (zoneEls[z]) zoneEls[z].g.classList.toggle("is-hot", on);
    zoneBtns.forEach((b) => { if (b.dataset.zone === z) b.classList.toggle("is-hot", on); });
    Object.keys(rows).forEach((r) => { if (rows[r].zone === z) rows[r].tr.classList.toggle("is-hot", on); });
  }

  // -- Events ----------------------------------------------------------------
  tabs.forEach((t) => t.addEventListener("click", () => choose(t.dataset.model)));
  root.querySelector(".layers-tabs").addEventListener("keydown", (e) => {
    const i = tabs.indexOf(document.activeElement);
    if (i < 0) return;
    const j = { ArrowRight: (i + 1) % tabs.length, ArrowLeft: (i - 1 + tabs.length) % tabs.length,
                Home: 0, End: tabs.length - 1 }[e.key];
    if (j === undefined) return;
    e.preventDefault();
    tabs[j].focus();
    choose(tabs[j].dataset.model);
  });
  const activate = (node, sel) => {
    node.addEventListener("click", () => select(sel));
    node.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(sel); }
    });
  };
  Object.keys(zoneEls).forEach((z) => {
    activate(zoneEls[z].g, { zone: z });
    zoneEls[z].g.addEventListener("mouseenter", () => hot(z, true));
    zoneEls[z].g.addEventListener("mouseleave", () => hot(z, false));
    zoneEls[z].g.addEventListener("focus", () => hot(z, true));
    zoneEls[z].g.addEventListener("blur", () => hot(z, false));
  });
  Object.keys(markerEls).forEach((k) => activate(markerEls[k], { marker: k }));
  zoneBtns.forEach((b) => {
    b.addEventListener("click", () => select({ zone: b.dataset.zone }));
    b.addEventListener("mouseenter", () => hot(b.dataset.zone, true));
    b.addEventListener("mouseleave", () => hot(b.dataset.zone, false));
  });
  markerBtns.forEach((b) => b.addEventListener("click", () => select({ marker: b.dataset.marker })));
  Object.keys(rows).forEach((r) => {
    const tr = rows[r].tr, z = rows[r].zone;
    tr.addEventListener("mouseenter", () => hot(z, true));
    tr.addEventListener("mouseleave", () => hot(z, false));
    tr.addEventListener("focusin", () => hot(z, true));
    tr.addEventListener("focusout", () => hot(z, false));
  });

  const toggle = root.querySelector(".stairs-toggle");
  const wrap = root.querySelector("#lr-stairs");
  const showText = toggle.textContent;
  toggle.addEventListener("click", () => {
    const open = toggle.getAttribute("aria-expanded") !== "true";
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    wrap.hidden = !open;
    toggle.textContent = open ? T.hide : showText;
  });

  update(false);
  if (document.fonts) document.fonts.ready.then(sizeLabels);
  window.matchMedia("(max-width: 1023px)").addEventListener("change", sizeLabels);
})();

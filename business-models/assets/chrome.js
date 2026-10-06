// Shared chrome for the business-models explainer pages (spec A5b): the slim
// two-row header (bar + AI Oy's growth-path stepper) and the family footer.
// BM_SITE below is the one page list both are rendered from, so a model or
// page is added in exactly one place and every page stays in sync.
//
// Each page provides the empty slots and says which page it is:
//   <body data-page="hub">  (or a model or page slug from the lists below)
//   <header id="bm-header" class="bm-header"></header> ... <footer id="bm-footer" class="bm-footer"></footer>
// and loads this script after them.
(function () {
  const SITE = {
    // Shown in the footer only: every page except the glossary already
    // carries it in its own kicker (approved design), so a header copy
    // would duplicate it; the footer is the glossary page's only marker.
    asOf: "Tilanne 9/2026",
    hub: "index.html",
    ecosystem: "../ecosystem.html",
    dashboard: "../index.html",
    family: "https://miikawir-ops.github.io/AI_valuechain/",
    // AI Oy's growth path, in order. Slugs double as the hub's deep-link
    // hashes (#gpu-cloud) and as the model card file names (gpu-cloud.html).
    models: [
      { slug: "public-cloud", name: "Julkinen pilvi" },
      { slug: "gpu-cloud", name: "GPU-pilvi" },
      { slug: "retail-colocation", name: "Retail-colocation" },
      { slug: "wholesale-colocation", name: "Wholesale-colocation" },
      { slug: "own-data-center", name: "Oma datakeskus" },
    ],
    // The other pages, linked from the header's top row (a "Sivut" menu on
    // narrow screens). Names are the pages' own titles from the design.
    pages: [
      { slug: "value-chain", name: "Arvoketju" },
      { slug: "financing", name: "Rahoitusmallit" },
      { slug: "specialised-models", name: "Erikoistuneet mallit" },
      { slug: "why-finland", name: "Miksi Suomi" },
      { slug: "glossary", name: "Sanasto" },
    ],
  };
  window.BM_SITE = SITE;

  const page = document.body.dataset.page || "";
  const isHub = page === "hub";
  // On the hub the stepper moves within the page (matrix columns / swipe
  // cards); elsewhere it navigates between the model card pages.
  const stepHref = (m) => (isHub ? "#" + m.slug : m.slug + ".html");
  const currentAttr = isHub ? "step" : "page";

  function esc(s) {
    return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  // The same links twice, from one list: inline on wide screens, in a
  // disclosure menu on narrow ones (CSS shows one or the other).
  function pagesNav() {
    const links = SITE.pages.map((pg) =>
      '<li><a href="' + esc(pg.slug) + '.html"' + (pg.slug === page ? ' aria-current="page"' : "") + ">"
      + esc(pg.name) + "</a></li>").join("");
    return '<nav class="bm-pages" aria-label="Sivut">'
      + '<ul class="bm-pages-list">' + links + "</ul>"
      + '<details class="bm-pages-menu"><summary>Sivut</summary><ul>' + links + "</ul></details>"
      + "</nav>";
  }

  const header = document.getElementById("bm-header");
  if (header) {
    const steps = SITE.models.map((m, i) =>
      '<li><a class="bm-step" href="' + esc(stepHref(m)) + '" data-step="' + esc(m.slug) + '"'
      + ' aria-label="Vaihe ' + (i + 1) + ": " + esc(m.name) + '"'
      + (m.slug === page ? ' aria-current="' + currentAttr + '"' : "") + ">"
      + '<span class="bm-step-num" aria-hidden="true">' + (i + 1) + "</span>"
      + '<span class="bm-step-name" aria-hidden="true">' + esc(m.name) + "</span></a></li>"
    ).join("");
    header.innerHTML =
      '<div class="bm-bar">'
      + '<a class="bm-back" href="' + SITE.ecosystem + '" aria-label="Takaisin ekosysteemikarttaan (englanninkielinen sivu)">'
      + '&larr; <span class="bm-back-long">Ekosysteemikartta</span><span class="bm-back-short">Ekosysteemi</span>'
      + '<span class="bm-lang" aria-hidden="true">EN</span></a>'
      + '<a class="bm-brand" href="' + SITE.hub + '"' + (isHub ? ' aria-current="page"' : "") + ">"
      + '<span class="bm-wordmark">Ray<span>Dar</span></span>'
      + '<span class="bm-brand-sub">Datakeskusten liiketoimintamallit</span></a>'
      + pagesNav()
      + "</div>"
      + '<nav class="bm-steps" aria-label="AI Oy:n kasvupolku">'
      + '<span class="bm-steps-label" aria-hidden="true">Kasvupolku</span>'
      + "<ol>" + steps + "</ol>"
      + '<span class="bm-steps-current" aria-hidden="true"></span>'
      + "</nav>";
  }

  const footer = document.getElementById("bm-footer");
  if (footer) {
    footer.innerHTML =
      "<div><strong>RayDar Data Center</strong> · Datakeskusten liiketoimintamallit · " + esc(SITE.asOf) + "</div>"
      + '<div class="bm-footer-note">Ei sijoitusneuvontaa · Opetuskäyttöön tarkoitettua taustatietoa</div>'
      + "<div>"
      + '<a href="' + SITE.dashboard + '">Dashboard (EN)</a> · '
      + '<a href="' + SITE.ecosystem + '">Ekosysteemikartta (EN)</a> · '
      + '<a href="' + SITE.family + '" target="_blank" rel="noopener">Osa RayDar-perhettä &#8599;</a>'
      + "</div>";
  }

  // Marks one stepper step as current (or none, with a falsy slug) and
  // mirrors its name next to the numbers on compact screens, where the
  // per-step names are hidden.
  function setActiveStep(slug) {
    const current = document.querySelector(".bm-steps-current");
    let name = "";
    document.querySelectorAll(".bm-step").forEach((a) => {
      const on = a.dataset.step === slug;
      if (on) {
        a.setAttribute("aria-current", currentAttr);
        name = a.querySelector(".bm-step-name").textContent;
      } else {
        a.removeAttribute("aria-current");
      }
    });
    if (current) current.textContent = name;
  }

  // Edge fade for .scroll-x rows: hidden once scrolled to the end, or when
  // the row doesn't overflow at all (wide screens).
  function watchScrollX(wrap) {
    const inner = wrap.querySelector(".scroll-x__inner");
    if (!inner) return;
    const update = () => {
      wrap.classList.toggle("is-end", inner.scrollLeft + inner.clientWidth >= inner.scrollWidth - 4);
    };
    inner.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    update();
  }
  document.querySelectorAll(".scroll-x").forEach(watchScrollX);

  // The "Sivut" menu closes on a click outside it or on Esc.
  const menu = document.querySelector(".bm-pages-menu");
  if (menu) {
    document.addEventListener("click", (e) => { if (menu.open && !menu.contains(e.target)) menu.open = false; });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && menu.open) { menu.open = false; menu.querySelector("summary").focus(); }
    });
  }

  window.BMChrome = { setActiveStep, watchScrollX };
  setActiveStep(page);
})();

// Shared chrome for the business-models explainer pages (spec A5b): the slim
// two-row header (bar + AI Oy's growth-path stepper) and the family footer.
// BM_SITE below is the one page list both are rendered from, so a model or
// page is added in exactly one place and every page stays in sync.
//
// Each page provides the empty slots and says which page it is:
//   <body data-page="hub">  (or a model or page slug from the lists below)
//   <header id="bm-header" class="bm-header"></header> ... <footer id="bm-footer" class="bm-footer"></footer>
// and loads this script after them.
//
// Finnish pages live in business-models/, their English versions under the
// same file names in business-models/en/ (ledger R104); the page's own
// <html lang> picks the language. The FI | EN switch in the bar keeps the
// page and the #hash.
(function () {
  const LANG = document.documentElement.lang === "en" ? "en" : "fi";
  const UP = LANG === "en" ? "../../" : "../";
  const TEXT = {
    fi: {
      // Review date: when the facts were last verified, not when a page was
      // last touched. Bump it only after an actual fact re-check (PLAN.md
      // step 8). Shown in the footer only: every page except the glossary
      // already carries it in its own kicker, so a header copy would duplicate
      // it; the footer is the glossary page's only marker.
      asOf: "Tiedot tarkistettu 9/2026",
      brandSub: "Datakeskusten liiketoimintamallit",
      pagesNav: "Sivut",
      stepsNav: "AI Oy:n kasvupolku",
      stepsLabel: "Kasvupolku",
      step: "Vaihe",
      langNav: "Kieli",
      // Family links to the two English sites: each screen-reader name starts
      // with the visible label (so voice control can target it) and says in
      // Finnish that the page is English.
      signalsAria: "Daily signals: päivittäiset signaalit ja pisteet (englanninkielinen sivu)",
      mapAria: "Ecosystem map: ekosysteemikartta (englanninkielinen sivu)",
      disclaimer: "Ei sijoitusneuvontaa · Opetuskäyttöön tarkoitettua taustatietoa",
      family: "Osa RayDar-perhettä",
      author: "Henkilökohtainen projekti · Miika Ray Wires",
      // AI Oy's growth path, in order. Slugs double as the hub's deep-link
      // hashes (#gpu-cloud) and as the model card file names (gpu-cloud.html).
      models: ["Julkinen pilvi", "GPU-pilvi", "Retail-colocation", "Wholesale-colocation", "Oma datakeskus"],
      // The pages linked from the header's top row (a "Sivut" menu on narrow
      // screens). Names are the pages' own titles from the design. The hub
      // comes first as "One pager", the design's own name for it, so it has a
      // visible link back from every page (Ray, 2026-10-08).
      pages: { hub: "One pager", "value-chain": "Arvoketju", financing: "Rahoitusmallit",
               "specialised-models": "Erikoistuneet mallit", "why-finland": "Miksi Suomi", glossary: "Sanasto" },
    },
    en: {
      asOf: "Content reviewed 9/2026",
      brandSub: "Data center business models",
      pagesNav: "Pages",
      stepsNav: "AI Ltd's growth path",
      stepsLabel: "Growth path",
      step: "Stage",
      langNav: "Language",
      signalsAria: "Daily signals: daily signals and scores",
      mapAria: "Ecosystem map: data center ecosystem map",
      disclaimer: "Not investment advice · Background information for educational use",
      family: "Part of the RayDar family",
      author: "Personal project · Miika Ray Wires",
      models: ["Public cloud", "GPU cloud", "Retail colocation", "Wholesale colocation", "Own data center"],
      pages: { hub: "One pager", "value-chain": "Value chain", financing: "Financing models",
               "specialised-models": "Specialized models", "why-finland": "Why Finland", glossary: "Glossary" },
    },
  }[LANG];
  const SLUGS = ["public-cloud", "gpu-cloud", "retail-colocation", "wholesale-colocation", "own-data-center"];
  const PAGE_SLUGS = ["hub", "value-chain", "financing", "specialised-models", "why-finland", "glossary"];
  const SITE = {
    asOf: TEXT.asOf,
    hub: "index.html",
    ecosystem: UP + "ecosystem.html",
    dashboard: UP + "index.html",
    family: "https://raydar.fi/",
    models: SLUGS.map((slug, i) => ({ slug, name: TEXT.models[i] })),
    // The hub's link points at the folder (business-models/ or
    // business-models/en/), the hub's canonical URL.
    pages: PAGE_SLUGS.map((slug) => ({ slug, name: TEXT.pages[slug], href: slug === "hub" ? "./" : undefined,
                                        lang: LANG === "fi" && slug === "hub" ? "en" : undefined })),
  };
  window.BM_SITE = SITE;

  const page = document.body.dataset.page || "";
  const isHub = page === "hub";
  // On the hub the stepper moves within the page (matrix columns / swipe
  // cards); elsewhere it navigates between the model card pages.
  const stepHref = (m) => (isHub ? "#" + m.slug : m.slug + ".html");
  const currentAttr = isHub ? "step" : "page";
  const fileOf = (slug) => (slug === "hub" ? "" : slug + ".html");

  function esc(s) {
    return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  // The same links twice, from one list: inline on wide screens, in a
  // disclosure menu on narrow ones (CSS shows one or the other).
  function pagesNav() {
    const links = SITE.pages.map((pg) =>
      '<li><a href="' + esc(pg.href || pg.slug + ".html") + '"' + (pg.lang ? ' lang="' + pg.lang + '"' : "")
      + (pg.slug === page ? ' aria-current="page"' : "") + ">"
      + esc(pg.name) + "</a></li>").join("");
    return '<nav class="bm-pages" aria-label="' + esc(TEXT.pagesNav) + '">'
      + '<ul class="bm-pages-list">' + links + "</ul>"
      + '<details class="bm-pages-menu"><summary>' + esc(TEXT.pagesNav) + "</summary><ul>" + links + "</ul></details>"
      + "</nav>";
  }

  // FI | EN: the current language as text, the other as a link to the same
  // page in that language. The #hash is added when the link is used, since
  // the hub rewrites it as the reader moves between models.
  function langSwitch() {
    if (!PAGE_SLUGS.concat(SLUGS).includes(page)) return "";
    const other = LANG === "fi" ? "en/" + fileOf(page) : "../" + fileOf(page);
    const item = (code, label) => (code === LANG
      ? '<span class="bm-lang-current" lang="' + code + '" aria-current="true">' + code.toUpperCase() + "</span>"
      : '<a class="bm-lang-link" href="' + esc(other) + '" lang="' + code + '" hreflang="' + code + '" aria-label="'
        + esc(label) + '">' + code.toUpperCase() + "</a>");
    return '<nav class="bm-lang" aria-label="' + esc(TEXT.langNav) + '">'
      + item("fi", "Suomeksi") + '<span class="bm-lang-sep" aria-hidden="true">|</span>' + item("en", "In English")
      + "</nav>";
  }

  function familyLink(href, icon, label, shortLabel, ariaLabel) {
    return '<a class="bm-family" href="' + href + '" hreflang="en" aria-label="' + esc(ariaLabel) + '">'
      + '<span class="bm-family-icon" aria-hidden="true">' + icon + "</span>"
      + '<span class="bm-family-long" lang="en">' + esc(label) + "</span>"
      + '<span class="bm-family-short" lang="en" aria-hidden="true">' + esc(shortLabel) + "</span></a>";
  }

  const header = document.getElementById("bm-header");
  if (header) {
    const steps = SITE.models.map((m, i) =>
      '<li><a class="bm-step" href="' + esc(stepHref(m)) + '" data-step="' + esc(m.slug) + '"'
      + ' aria-label="' + esc(TEXT.step) + " " + (i + 1) + ": " + esc(m.name) + '"'
      + (m.slug === page ? ' aria-current="' + currentAttr + '"' : "") + ">"
      + '<span class="bm-step-num" aria-hidden="true">' + (i + 1) + "</span>"
      + '<span class="bm-step-name" aria-hidden="true">' + esc(m.name) + "</span></a></li>"
    ).join("");
    header.innerHTML =
      '<div class="bm-bar">'
      // Family links to the two English sites, styled like the family-link
      // cards on the dashboard and ecosystem page (same gradient and icons).
      + familyLink(SITE.dashboard, "📈", "Daily signals", "Signals", TEXT.signalsAria)
      + familyLink(SITE.ecosystem, "🗺️", "Ecosystem map", "Map", TEXT.mapAria)
      + '<a class="bm-brand" href="' + SITE.hub + '"' + (isHub ? ' aria-current="page"' : "") + ">"
      + '<span class="bm-wordmark">Ray<span>Dar</span></span>'
      + '<span class="bm-brand-sub">' + esc(TEXT.brandSub) + "</span></a>"
      + pagesNav()
      + langSwitch()
      + "</div>"
      + '<nav class="bm-steps" aria-label="' + esc(TEXT.stepsNav) + '">'
      + '<span class="bm-steps-label" aria-hidden="true">' + esc(TEXT.stepsLabel) + "</span>"
      + "<ol>" + steps + "</ol>"
      + '<span class="bm-steps-current" aria-hidden="true"></span>'
      + "</nav>";
    const sw = header.querySelector(".bm-lang-link");
    if (sw) {
      const base = sw.getAttribute("href");
      const withHash = () => { sw.setAttribute("href", base + location.hash); };
      ["pointerdown", "focus", "click"].forEach((ev) => sw.addEventListener(ev, withHash));
    }
  }

  const footer = document.getElementById("bm-footer");
  if (footer) {
    footer.innerHTML =
      "<div><strong>RayDar Data Center</strong> · " + esc(TEXT.brandSub) + " · " + esc(SITE.asOf) + "</div>"
      + '<div class="bm-footer-note">' + esc(TEXT.disclaimer) + "</div>"
      + "<div>"
      + '<a href="' + SITE.dashboard + '" hreflang="en" lang="en">Daily signals</a> · '
      + '<a href="' + SITE.ecosystem + '" hreflang="en" lang="en">Ecosystem map</a> · '
      + '<a href="' + SITE.family + '" target="_blank" rel="noopener">' + esc(TEXT.family) + " &#8599;</a>"
      + "</div>"
      + '<div class="bm-footer-note">' + esc(TEXT.author) + "</div>";
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

  // The "Sivut" / "Pages" menu closes on a click outside it or on Esc.
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

// ecosystem-data.v3.js — single source of truth for the interactive Data
// Center Ecosystem map. Diagram arrows, the legend, the side panel, and the
// poster hotspots are all generated from this file, so they can't drift
// apart the way the static poster image's arrow colors drifted from its
// own legend.
//
// Versioned filename: any future content edit gets a new suffix (v2, v3...)
// rather than reusing this one, so browser/CDN caches can't silently serve
// stale content (the same lesson as the poster image rename). v2 added
// posterBox/panelRegion/POSTER_GROUPS. v3 adds posterAccent, GLOSSARY,
// MONEY_WALKTHROUGH_STEPS, CONTENT_REVIEWED.
//
// Accuracy (CLAUDE.md): general mechanisms below are not independently
// cited. The one named real-world example (Fortum/Microsoft, Espoo &
// Kirkkonummi) is sourced — see CASE_STUDY.sources and the explanation
// section in ecosystem.html, which cites the same sources. DSO and
// district-heating stakeholder descriptions deliberately say "e.g." before
// naming a company — Finland has many DSOs and district heating companies,
// so naming one as *the* operator would be inaccurate.
//
// posterBox {x,y,w,h} — % of assets/ecosystem-v2.webp (1536x966), measured
// directly off the image (crop+zoom per region, read pixel edges), not
// estimated. The source poster has one "Grid & Transmission (TSO)" box
// covering both transmission and distribution — dso has no posterBox of
// its own; see POSTER_GROUPS below for how it's folded into tso's box.
//
// posterAccent — each stakeholder's illustrated neon border color, sampled
// directly from the image (max-saturation pixel along the box's border),
// not chosen by eye. Used only for the compact/full panel's accent stripe —
// the hotspot's own selection glow stays the uniform family blue/purple
// language, since that's a "this is selected" affordance, not a category
// color, and conflating the two would make selection state harder to read.

const FLOW_TYPES = {
  energy:   { label: "Energy / Heat",        color: "#639922" },
  goods:    { label: "Goods / Services",     color: "#378ADD" },
  contract: { label: "Contract / Agreement", color: "#534AB7" },
  data:     { label: "Data",                 color: "#E24B4A" },
  capital:  { label: "Capital / Financing",  color: "#EF9F27" },
};

// Fixed hand-tuned layout, viewBox 0 0 1000 700.
const STAKEHOLDERS = [
  { id: "operator", name: "Data Center Operator", x: 500, y: 360,
    description: "Runs the facility itself — as a colocation provider (rents space, power, and cooling to many customers), a hyperscaler operating its own site, or a third-party operator managing it on behalf of an owner.",
    posterBox: { x: 32.8, y: 40.2, w: 20.4, h: 10.8 }, posterAccent: "#02AAEA" },

  { id: "public_sector", name: "Public Sector / Municipality", x: 350, y: 80,
    description: "Grants zoning, land use, and permits, and coordinates infrastructure access for new data center developments.",
    posterBox: { x: 36.5, y: 9.7, w: 17.0, h: 9.7 }, posterAccent: "#44059C" },
  { id: "construction", name: "Construction & Real Estate", x: 650, y: 80,
    description: "Land and site developers, construction contractors, and permitting specialists who build the physical facility.",
    posterBox: { x: 55.5, y: 16.5, w: 16.7, h: 7.7 }, posterAccent: "#21E4FF" },

  { id: "energy_gen", name: "Energy & Power Generation", x: 100, y: 140,
    description: "Producers supplying the grid — renewables (wind, solar, hydro), nuclear, gas, and other sources — that a data center's power ultimately comes from.",
    posterBox: { x: 2.1, y: 19.7, w: 16.7, h: 9.8 }, posterAccent: "#008644" },
  { id: "tso", name: "Transmission (TSO)", x: 100, y: 230,
    description: "Operates the national high-voltage transmission grid and substations. In Finland: Fingrid.",
    posterBox: { x: 19.9, y: 17.7, w: 17.9, h: 8.4 }, posterAccent: "#25E5FF" },
  { id: "dso", name: "Distribution (DSO)", x: 100, y: 320,
    description: "Operates regional and local electricity distribution networks, separate from the national transmission grid — e.g. Caruna in Finland." },
    // no posterBox: the source poster has one combined "Grid & Transmission
    // (TSO)" box — see POSTER_GROUPS, which folds dso into tso's box.
  { id: "district_heating", name: "District Heating / Energy Recovery", x: 100, y: 410,
    description: "Utilities capturing a data center's waste heat and distributing it as district heating (kaukolämpö) to homes, offices, and industrial users — e.g. Fortum in Finland.",
    posterBox: { x: 2.1, y: 33.0, w: 18.0, h: 9.7 }, posterAccent: "#CA3D6A" },
  { id: "cooling", name: "Cooling & HVAC Suppliers", x: 100, y: 500,
    description: "Suppliers of chillers, cooling systems, liquid cooling, and heat rejection equipment.",
    posterBox: { x: 2.1, y: 43.8, w: 17.4, h: 10.0 }, posterAccent: "#2DCBEC" },
  { id: "backup_power", name: "Backup Power & Fuel", x: 100, y: 590,
    description: "Suppliers of generators, fuel, UPS systems, and backup power distribution.",
    posterBox: { x: 2.1, y: 55.5, w: 17.4, h: 11.6 }, posterAccent: "#D4A017" },

  { id: "equipment", name: "Equipment & Technology Suppliers", x: 900, y: 140,
    description: "Suppliers of compute (GPU/ASIC) hardware and power/electrical equipment for the facility.",
    posterBox: { x: 58.4, y: 27.0, w: 18.9, h: 12.8 }, posterAccent: "#22DCF8" },
  { id: "capital", name: "Capital & Finance", x: 900, y: 230,
    description: "Infrastructure funds, data center REITs, lenders, and equity partners financing construction and operation.",
    posterBox: { x: 61.2, y: 42.2, w: 15.2, h: 9.6 }, posterAccent: "#1CBAE0" },
  { id: "hyperscaler", name: "Hyperscaler / Cloud", x: 900, y: 320,
    description: "Large cloud platforms — Microsoft, Google, Amazon, and similar — buying or operating compute capacity, serving their own external customers.",
    posterBox: { x: 61.2, y: 54.9, w: 16.1, h: 9.7 }, posterAccent: "#AD2661" },

  { id: "network", name: "Network & Connectivity", x: 650, y: 620,
    description: "Suppliers of fiber, cabling, switches, routers, optical transport, and interconnection.",
    posterBox: { x: 22.0, y: 65.1, w: 16.2, h: 9.8 }, posterAccent: "#0679AB" },
  { id: "storage", name: "Storage Providers", x: 500, y: 650,
    description: "Suppliers of storage arrays, data protection, and backup & recovery systems.",
    posterBox: { x: 39.9, y: 65.6, w: 16.0, h: 9.3 }, posterAccent: "#099FBC" },
  { id: "enterprise", name: "Enterprise & End Users", x: 350, y: 620,
    description: "Businesses, developers, and consumers — the end users of the compute, storage, and connectivity a data center provides.",
    posterBox: { x: 55.8, y: 64.8, w: 16.3, h: 10.1 }, posterAccent: "#5C2FB0" },
];

// Poster-only grouping: stakeholders that share one illustrated box in the
// source poster image. Keyed by the id that owns the posterBox; each entry
// lists the id(s) folded into that box for hotspot/highlight/panel purposes
// on the poster view only — the Relationship explorer and mobile list keep
// tso/dso fully separate.
const POSTER_GROUPS = {
  tso: {
    extraIds: ["dso"],
    panelLabel: "Grid: transmission & distribution",
    subLabels: { tso: "TSO (Fingrid)", dso: "DSO (e.g. Caruna)" },
  },
};

// Overlay panel placement on the poster, matching the illustration's
// "Selected stakeholder" panel region (% of image). If the panel renders
// narrower than ~320px at a given width, ecosystem.html falls back to
// placing the panel below the image instead of overlaying it.
const PANEL_REGION = { x: 78.8, y: 2.3, w: 20.4, h: 64.8 };

// "added: true" entries are not literal arrows from the source poster image —
// flagged explicitly rather than presented as if they were always there.
const RELATIONSHIPS = [
  { from: "public_sector",     to: "operator",  type: "contract", label: "Permits & land use",
    explanation: "The municipality grants zoning, land use, and construction permits the operator needs to build and run the facility." },
  { from: "construction",      to: "operator",  type: "goods",    label: "Construction services",
    explanation: "Construction firms build and hand over the physical facility to the operator." },
  { from: "energy_gen",        to: "operator",  type: "energy",   label: "PPA / green energy",
    explanation: "The operator often signs a long-term power purchase agreement (PPA) with a renewable energy producer, fixing the price for an agreed volume of electricity." },
  { from: "tso",                to: "operator",  type: "energy",   label: "Grid access & connection",
    explanation: "Large facilities connect directly to the national transmission grid via the TSO." },
  { from: "dso",                to: "operator",  type: "energy",   label: "Regional/local grid connection", added: true,
    explanation: "Smaller or regionally-connected facilities draw power through the local distribution network instead of a direct transmission connection." },
  { from: "district_heating",  to: "operator",  type: "energy",   label: "Waste heat (heat sales)",
    explanation: "The operator can sell captured waste heat from its cooling systems into a district heating network instead of releasing it into the air." },
  { from: "cooling",            to: "operator",  type: "goods",    label: "Cooling systems & services",
    explanation: "Cooling suppliers provide and maintain the chillers, liquid cooling, and heat rejection systems that keep the facility running." },
  { from: "backup_power",      to: "operator",  type: "goods",    label: "Backup power & fuel",
    explanation: "Backup power suppliers provide generators, fuel, and UPS systems for outage protection." },
  { from: "network",            to: "operator",  type: "goods",    label: "Connectivity & bandwidth",
    explanation: "Network suppliers provide the fiber, switches, and interconnection that link the facility to the wider internet." },
  { from: "storage",            to: "operator",  type: "goods",    label: "Storage & data services",
    explanation: "Storage suppliers provide the arrays and systems used for data protection and backup." },
  { from: "equipment",          to: "operator",  type: "goods",    label: "Equipment & components",
    explanation: "Equipment suppliers provide the compute hardware and electrical equipment installed inside the facility." },
  { from: "capital",            to: "operator",  type: "capital",  label: "Financing & investment",
    explanation: "Infrastructure funds, REITs, and lenders finance the facility's construction and ongoing operation." },
  { from: "hyperscaler",       to: "operator",  type: "contract", label: "Lease & services (compute capacity)",
    explanation: "A hyperscaler leases capacity from the operator, or is the operator itself if it self-operates the facility." },
  { from: "hyperscaler",       to: "enterprise", type: "goods",   label: "Cloud services", added: true,
    explanation: "Hyperscalers sell compute, storage, and networking as an ongoing service to businesses and developers." },
  { from: "energy_gen",        to: "tso",       type: "energy",   label: "Power fed into the grid", added: true,
    explanation: "Electricity producers feed power into the national transmission grid." },
  { from: "tso",                to: "dso",       type: "energy",   label: "Transmission to distribution", added: true,
    explanation: "Power moves from the national transmission grid down into regional and local distribution networks." },
  { from: "capital",            to: "construction", type: "capital", label: "Project & development financing", added: true,
    explanation: "Financiers often fund the construction and development phase directly, before or alongside financing the operator." },
];

const WALKTHROUGH_STEPS = [
  { title: "1. Land & permits", highlightIds: ["public_sector", "operator"],
    description: "Before anything is built, the operator needs land and permits from the public sector — zoning, land use, and construction approvals." },
  { title: "2. Financing", highlightIds: ["capital", "construction", "operator"],
    description: "Construction is funded through a mix of infrastructure funds, REITs, and lenders, often before the site is fully built." },
  { title: "3. Construction", highlightIds: ["construction", "operator"],
    description: "Construction and real estate firms develop the site and put up the building." },
  { title: "4. Grid connection & power", highlightIds: ["energy_gen", "tso", "dso", "operator"],
    description: "The facility connects to the grid — via the transmission operator (TSO) for large direct connections, or a distribution operator (DSO) for regional supply — and often secures a long-term power purchase agreement (PPA) with a renewable energy producer." },
  { title: "5. Equipment", highlightIds: ["equipment", "cooling", "network", "storage", "backup_power", "operator"],
    description: "Compute, networking, storage, cooling, and backup power equipment are installed by specialist suppliers." },
  { title: "6. Customers", highlightIds: ["operator", "hyperscaler", "enterprise"],
    description: "Capacity reaches customers in different forms: operators lease colocation space (retail or wholesale), landlords lease powered shells, and hyperscalers sell cloud services to businesses." },
  { title: "7. Waste heat", highlightIds: ["district_heating", "operator"],
    description: "Heat generated by the facility's cooling systems can be captured and sold into a district heating network instead of released into the air." },
];

const CASE_STUDY = {
  title: "Fortum × Microsoft, Espoo & Kirkkonummi, Finland",
  body: "Fortum's heat pump plants at Kolabacken (Kirkkonummi) and Hepokorpi (Espoo) started operating in spring 2026, today producing district heat from ambient air and electric boilers. Waste-heat recovery from Microsoft's nearby data centers begins step by step from 2027. Once fully implemented, the project is expected to supply around 40% of the roughly 2 TWh yearly district heat demand of about 250,000 users across Espoo, Kauniainen, and Kirkkonummi — involving the data center operator (Microsoft, which both builds and runs its own facilities here), the district heating utility (Fortum), two municipalities (Espoo and Kirkkonummi), the distribution operator (Caruna), and the transmission operator (Fingrid).",
  highlightIds: ["operator", "hyperscaler", "district_heating", "public_sector", "dso", "tso"],
  sources: [
    { label: "Fortum — \"Fortum has started heat production at two large data centre sites in Finland\" (May 2026, primary)",
      url: "https://www.fortum.com/en/media/2026/05/fortum-has-started-heat-production-two-large-data-centre-sites-finland" },
    { label: "Microsoft — official announcement (2022, background)",
      url: "https://news.microsoft.com/europe/2022/03/17/microsoft-announces-intent-to-build-a-new-datacenter-region-in-finland-accelerating-sustainable-digital-transformation-and-enabling-large-scale-carbon-free-district-heating/" },
  ],
};

// Second guided walkthrough: who pays whom. Business relationships only,
// deliberately no tax framing (Ray's instruction). Drafted from and
// consistent with RELATIONSHIPS above — no new facts, just a payment-
// direction framing of the same relationships.
const MONEY_WALKTHROUGH_STEPS = [
  { title: "1. Customers pay for capacity", highlightIds: ["enterprise", "hyperscaler", "operator"],
    description: "Enterprises and hyperscalers pay data center operators for colocation space, landlords receive rent for powered shells, and enterprises pay hyperscalers for cloud services." },
  { title: "2. Paying for the build", highlightIds: ["operator", "construction", "capital"],
    description: "The operator or developer pays construction firms to build the facility, largely funded up front by lenders and investors." },
  { title: "3. The operator pays its suppliers", highlightIds: ["operator", "equipment", "cooling", "network", "storage", "backup_power"],
    description: "The operator pays equipment, cooling, network, storage and backup power suppliers for the hardware and systems that keep the facility running." },
  { title: "4. The operator pays for energy", highlightIds: ["operator", "energy_gen", "tso", "dso"],
    description: "The operator pays for electricity, through a supplier or the market, often combined with a long-term PPA with a producer, plus network fees to the grid operator it's connected to (usually the DSO; the TSO for large direct connections)." },
  { title: "5. Returns to capital providers", highlightIds: ["operator", "capital"],
    description: "Lenders receive interest and repayments, equity investors such as infrastructure funds receive returns, and where a REIT owns the building, the operator pays it rent." },
  { title: "6. Heat flows back as revenue", highlightIds: ["operator", "district_heating"],
    description: "Where waste heat is captured and sold into a district heating network, money flows the other way: the district heating company pays the operator for the heat." },
];

// Glossary — dotted-underlined terms in the explanation card link here.
// Definitions kept to one line each; consistent with (not adding facts
// beyond) the explanation card's own prose.
const GLOSSARY = {
  ppa: { term: "PPA", definition: "Power purchase agreement. A long-term contract to buy electricity from a specific generator, often a renewable project, typically at a fixed or pre-agreed price. The power itself usually flows through the shared grid." },
  tso: { term: "TSO", definition: "Transmission system operator: runs the national high-voltage electricity grid. In Finland: Fingrid." },
  dso: { term: "DSO", definition: "Distribution system operator: runs regional and local electricity networks — e.g. Caruna in Finland." },
  powered_shell: { term: "Powered shell", definition: "A lease where the landlord provides the building and power connection, and the tenant fits out its own cooling and electrical systems." },
  reit: { term: "REIT", definition: "Real estate investment trust: a company that owns income-producing property (like data centers) and leases it out for rental income." },
  colocation: { term: "Colocation", definition: "Renting space, power, and cooling inside a shared data center facility, rather than building and operating your own." },
  retail_colocation: { term: "Retail colocation", definition: "Renting racks or a cage inside a shared data center hall." },
  wholesale_colocation: { term: "Wholesale colocation", definition: "Leasing an entire dedicated hall or building within a data center, typically on a long-term contract." },
};

// Shown on the page and used as a PLAN.md review-cadence reminder — content
// (especially the Fortum/Microsoft case study) should be re-checked
// periodically since real projects move; see PLAN.md.
const CONTENT_REVIEWED = "September 2026";

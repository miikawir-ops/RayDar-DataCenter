// ecosystem-data.v9.js — single source of truth for the interactive Data
// Center Ecosystem map. Diagram arrows, the legend, the side panel, and the
// poster hotspots are all generated from this file, so they can't drift
// apart the way the static poster image's arrow colors drifted from its
// own legend.
//
// Versioned filename: any future content edit gets a new suffix (v2, v3...)
// rather than reusing this one, so browser/CDN caches can't silently serve
// stale content (the same lesson as the poster image rename). v2 added
// posterBox/panelRegion/POSTER_GROUPS. v3 added posterAccent, GLOSSARY,
// MONEY_WALKTHROUGH_STEPS, CONTENT_REVIEWED. v4 clarifies the equipment
// stakeholder's description (it listed cooling/storage/networking/backup
// power as its own bullets while those already have dedicated stakeholder
// nodes elsewhere on the map — contradicted the poster's own box). v5
// (2026-10-09, PLAN.md ledger R19/R20): FLOW_TYPES colours sampled from the
// poster's own legend arrows (the earlier muted values didn't match it —
// contract was indigo where the poster's legend is magenta); the explorer's
// bottom row spread so Storage no longer overlaps Network and Enterprise;
// PANEL_REGION.railBottom added for the card that follows the reader; one
// Data relationship (enterprise -> hyperscaler), so the Data flow type is
// used and its filter chip does something (R24). v6 (2026-10-09, R26):
// payer -> payee pairs on each "Follow the money" step (drawn as money arrows
// over the poster and listed in the card, from this one source), and the
// waste-heat relationship now points the way the heat flows; R27: so does
// the leased-capacity relationship (operator -> hyperscaler), and money
// step 4's text says the PPA fixes the price. v7 (2026-10-09, R29): the
// poster's printed label boxes (POSTER_LABELS), so money badges avoid them.
// v8 (2026-10-10, R31): the operator -> enterprise colocation relationship.
// v9 (2026-10-11, R52/R53): money step 7 (the public sector's share), the
// hyperscaler note in step 1 and the Daily signals link in step 3; the GPU
// cloud (neocloud) stakeholder and its relationships; EXAMPLES, sourced
// companies per stakeholder.
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

// Colours sampled from the poster's own legend arrows (median of each
// arrow's most saturated, brightest pixels; assets/ecosystem-v2.webp, legend
// row y 827-839), so the explorer, the legend chips and the panels use the
// poster's palette. Measured, not chosen by eye.
const FLOW_TYPES = {
  energy:   { label: "Energy / Heat",        color: "#8AFAC1" },
  goods:    { label: "Goods / Services",     color: "#12E5FB" },
  contract: { label: "Contract / Agreement", color: "#E167FB" },
  data:     { label: "Data",                 color: "#F95E94" },
  capital:  { label: "Capital / Financing",  color: "#FDE826" },
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
    description: "Suppliers of compute (GPU/ASIC) hardware and power/electrical equipment for the facility. Cooling, storage, networking and backup power suppliers are shown as their own stakeholders on the map.",
    posterBox: { x: 58.4, y: 27.0, w: 18.9, h: 12.8 }, posterAccent: "#22DCF8" },
  { id: "capital", name: "Capital & Finance", x: 900, y: 230,
    description: "Infrastructure funds, data center REITs, lenders, and equity partners financing construction and operation.",
    posterBox: { x: 61.2, y: 42.2, w: 15.2, h: 9.6 }, posterAccent: "#1CBAE0" },
  { id: "hyperscaler", name: "Hyperscaler / Cloud", x: 900, y: 320,
    description: "Large cloud platforms — Microsoft, Google, Amazon, and similar — buying or operating compute capacity, serving their own external customers.",
    posterBox: { x: 61.2, y: 54.9, w: 16.1, h: 9.7 }, posterAccent: "#AD2661" },

  { id: "network", name: "Network & Connectivity", x: 710, y: 620,
    description: "Suppliers of fiber, cabling, switches, routers, optical transport, and interconnection.",
    posterBox: { x: 22.0, y: 65.1, w: 16.2, h: 9.8 }, posterAccent: "#0679AB" },
  { id: "storage", name: "Storage Providers", x: 500, y: 650,
    description: "Suppliers of storage arrays, data protection, and backup & recovery systems.",
    posterBox: { x: 39.9, y: 65.6, w: 16.0, h: 9.3 }, posterAccent: "#099FBC" },
  // GPU cloud (R52/R53): no box of its own on the poster, so it shares the
  // Hyperscaler / Cloud box there (POSTER_GROUPS), like the DSO and the grid.
  { id: "neocloud", name: "GPU Cloud (Neocloud)", x: 900, y: 430,
    description: "Specialist cloud companies that rent out GPU computing for AI, usually as dedicated capacity, rather than the broad range of services a hyperscaler sells. They lease space from colocation operators or build their own sites, and sell capacity to AI developers, businesses and the hyperscalers themselves." },
  { id: "enterprise", name: "Enterprise & End Users", x: 290, y: 620,
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
  hyperscaler: {
    extraIds: ["neocloud"],
    panelLabel: "Cloud: hyperscalers & GPU clouds",
    subLabels: { hyperscaler: "Hyperscaler / Cloud", neocloud: "GPU Cloud (Neocloud)" },
  },
};

// Overlay panel placement on the poster, matching the illustration's
// "Selected stakeholder" panel region (% of image). If the panel renders
// narrower than ~320px at a given width, ecosystem.html falls back to
// placing the panel below the image instead of overlaying it.
// railBottom: how far down the right-hand column the selected-stakeholder
// card may travel as the reader scrolls — just above the poster's legend
// panel, whose top border is at 74.4% (y 719 of 966), measured at x 82%, 88%
// and 94%.
const PANEL_REGION = { x: 78.8, y: 2.3, w: 20.4, h: 64.8, railBottom: 73.5 };

// The poster's printed relationship labels (the pills on its arrows), as %
// of assets/ecosystem-v2.webp (1536x966). Measured from the image: each
// pill's border found by pixel scanning and checked on an overlay; "Backup
// power & fuel" measured by eye on that overlay. The money arrows' euro
// badges are placed so they never cover one of these or a stakeholder box
// (R29, 2026-10-09).
const POSTER_LABELS = [
  { label: "Permits & land use", x: 38.8, y: 21.3, w: 4.4, h: 4.3 },
  { label: "Construction services", x: 47.9, y: 23.6, w: 5.1, h: 4.5 },
  { label: "PPA / green energy (electricity)", x: 21.6, y: 28.9, w: 6.9, h: 4.3 },
  { label: "Grid access & connection", x: 32.7, y: 27.2, w: 4.9, h: 4.2 },
  { label: "Waste heat (heat sales)", x: 22.8, y: 35.7, w: 4.6, h: 4.0 },
  { label: "Equipment & components", x: 51.4, y: 32.8, w: 5.7, h: 5.0 },
  { label: "Cooling systems & services", x: 22.5, y: 45.3, w: 5.7, h: 4.3 },
  { label: "Financing & investment", x: 53.6, y: 43.7, w: 5.2, h: 4.1 },
  { label: "Lease & services (compute capacity)", x: 52.2, y: 53.4, w: 6.6, h: 4.1 },
  { label: "Backup power & fuel", x: 23.8, y: 55.1, w: 6.2, h: 4.5 },
  { label: "Connectivity & bandwidth", x: 31.3, y: 57.2, w: 5.3, h: 4.1 },
  { label: "Storage & data services", x: 41.7, y: 58.9, w: 5.8, h: 4.2 },
];

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
  // Points the way the heat flows: from the operator to the district heating
  // network (R26). It used to point at the operator like every other
  // relationship, which read as heat flowing into the data center; the money
  // flows the other way and is shown in the "Follow the money" walkthrough.
  { from: "operator",           to: "district_heating", type: "energy", label: "Waste heat (heat sales)",
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
  // Points the way the capacity flows: the operator leases it to the
  // hyperscaler (R27). It used to point at the operator like the supply
  // arrows, which read as the hyperscaler supplying the operator; the rent
  // flows the other way, in "Follow the money" step 1.
  { from: "operator",           to: "hyperscaler", type: "contract", label: "Lease & services (compute capacity)",
    explanation: "A hyperscaler leases capacity from the operator, or is the operator itself if it self-operates the facility." },
  { from: "hyperscaler",       to: "enterprise", type: "goods",   label: "Cloud services", added: true,
    explanation: "Hyperscalers sell compute, storage, and networking as an ongoing service to businesses and developers." },
  // Retail colocation (R31, 2026-10-10): the poster draws this arrow (an
  // unlabelled two-headed Contract arrow), money step 1 charges it, and the
  // life path's step 6 describes it. It points the way the space flows; the
  // colocation fees flow back in "Follow the money" step 1.
  { from: "operator",           to: "enterprise", type: "contract", label: "Colocation (space, power & cooling)", added: true,
    explanation: "Businesses rent space in the operator's facility for their own servers, usually racks or a cage in a shared hall (retail colocation), with power and cooling supplied by the operator and often direct connections to carriers and cloud providers in the same building." },
  // The model's only Data relationship (R24, 2026-10-09): the data the whole
  // system exists to process. Deliberately not operator <-> tenant: in
  // colocation the operator supplies space, power and cooling, and the
  // tenant's own servers handle the data.
  { from: "enterprise",        to: "hyperscaler", type: "data",   label: "Data & workloads", added: true,
    explanation: "Businesses and developers send their data and computing workloads to the cloud platform, which stores and processes them in its data centers and returns the results." },
  { from: "energy_gen",        to: "tso",       type: "energy",   label: "Power fed into the grid", added: true,
    explanation: "Electricity producers feed power into the national transmission grid." },
  { from: "tso",                to: "dso",       type: "energy",   label: "Transmission to distribution", added: true,
    explanation: "Power moves from the national transmission grid down into regional and local distribution networks." },
  { from: "capital",            to: "construction", type: "capital", label: "Project & development financing", added: true,
    explanation: "Financiers often fund the construction and development phase directly, before or alongside financing the operator." },
  // GPU cloud (neocloud) relationships (R52/R53).
  { from: "operator",           to: "neocloud", type: "contract", label: "Colocation (space, power & cooling)", added: true,
    explanation: "A GPU cloud often rents space, power and cooling in an operator's facility for its GPU servers; some build and run their own sites instead." },
  { from: "equipment",          to: "neocloud", type: "goods",    label: "GPUs & servers", added: true,
    explanation: "GPU clouds buy GPU servers and networking equipment from equipment suppliers; the GPUs are their main asset." },
  { from: "capital",            to: "neocloud", type: "capital",  label: "Debt & equity financing", added: true,
    explanation: "Building GPU clusters takes large up-front investment, financed with equity and debt." },
  { from: "neocloud",           to: "enterprise", type: "goods",  label: "GPU capacity as a service", added: true,
    explanation: "AI developers and businesses rent GPU capacity, on demand or under longer contracts." },
  { from: "neocloud",           to: "hyperscaler", type: "contract", label: "GPU capacity contracts", added: true,
    explanation: "Hyperscalers also buy GPU capacity from GPU clouds to meet demand without building it all themselves — for example, Microsoft's five-year agreement with Nebius, announced in September 2025." },
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

// Second guided walkthrough: who pays whom. Drafted from and consistent with
// RELATIONSHIPS above. Step 7, the public sector's share (R52/R53), adds the
// public-sector payments in general terms, each checked against official
// sources (its `sources`); `note` is a dated Finland-specific line.
const MONEY_WALKTHROUGH_STEPS = [
  { title: "1. Customers pay for capacity", highlightIds: ["enterprise", "hyperscaler", "neocloud", "operator"],
    description: "Enterprises and hyperscalers pay data center operators for colocation space, landlords receive rent for powered shells, and enterprises pay hyperscalers for cloud services. In a hyperscaler's own facility there is no rent: the hyperscaler builds and operates the site itself — Google's data center in Hamina is one example.",
    payments: [
      { from: "enterprise",  to: "hyperscaler", what: "cloud service fees" },
      { from: "hyperscaler", to: "operator",    what: "rent for leased capacity" },
      { from: "enterprise",  to: "operator",    what: "colocation fees" },
      { from: "enterprise",  to: "neocloud",    what: "GPU capacity fees" },
      { from: "hyperscaler", to: "neocloud",    what: "GPU capacity contracts" },
    ],
    sources: [
      { label: "DCD — Google to invest in a second facility in Hamina, at its own site in the former Summa paper mill",
        url: "https://www.datacenterdynamics.com/en/news/google-invest-670m-to-build-second-facility-hamina-finland-/" },
    ] },
  { title: "2. Paying for the build", highlightIds: ["operator", "construction", "capital"],
    description: "The operator or developer pays construction firms to build the facility, largely funded up front by lenders and investors.",
    payments: [
      { from: "operator", to: "construction", what: "construction contracts" },
      { from: "capital",  to: "operator",     what: "loans and equity" },
      { from: "capital",  to: "construction", what: "development financing" },
    ] },
  { title: "3. The operator pays its suppliers", highlightIds: ["operator", "equipment", "cooling", "network", "storage", "backup_power"],
    description: "The operator pays equipment, cooling, network, storage and backup power suppliers for the hardware and systems that keep the facility running.",
    link: { href: "index.html", text: "This spending is the investment flow the Daily signals page tracks →" },
    payments: [
      { from: "operator", to: "equipment",    what: "compute and electrical equipment" },
      { from: "operator", to: "cooling",      what: "cooling systems and service" },
      { from: "operator", to: "network",      what: "connectivity" },
      { from: "operator", to: "storage",      what: "storage systems" },
      { from: "operator", to: "backup_power", what: "generators, fuel and UPS systems" },
    ] },
  { title: "4. The operator pays for energy", highlightIds: ["operator", "energy_gen", "tso", "dso"],
    description: "The operator pays for electricity, through a supplier or the market, often combined with a long-term PPA, which fixes the price with a producer, plus network fees to the grid operator it's connected to (usually the DSO; the TSO for large direct connections).",
    payments: [
      { from: "operator", to: "energy_gen", what: "electricity, often under a long-term PPA" },
      { from: "operator", to: "dso",        what: "network fees (to the TSO instead, for large direct connections)" },
    ] },
  { title: "5. Returns to capital providers", highlightIds: ["operator", "capital"],
    description: "Lenders receive interest and repayments, equity investors such as infrastructure funds receive returns, and where a REIT owns the building, the operator pays it rent.",
    payments: [
      { from: "operator", to: "capital", what: "interest and repayments, investor returns, and rent where a REIT owns the building" },
    ] },
  { title: "6. Heat flows back as revenue", highlightIds: ["operator", "district_heating"],
    description: "Where waste heat is captured and sold into a district heating network, money flows the other way: the district heating company pays the operator for the heat.",
    payments: [
      { from: "district_heating", to: "operator", what: "payment for the waste heat" },
    ] },
  { title: "7. The public sector's share", highlightIds: ["public_sector", "operator"],
    description: "The public sector is paid along the way. Where a municipality owns the land, it receives the sale price or rent, and its building control charges fees for permits. Once the facility stands, its owner pays property tax to that municipality every year. The state collects electricity tax through the electricity bill. Income taxes are shared: the operator's corporate income tax goes to the state and municipalities, and its employees' income tax to the state and their home municipalities.",
    note: "In Finland, data centres paid the lower electricity tax class until 30 June 2026 and have paid the general class since 1 July 2026: an energy tax of 2.24 c/kWh instead of 0.05 c/kWh. A ten-year tax-relief scheme the Government decided on in December 2025 was dropped in September 2026. (Reviewed 10/2026.)",
    payments: [
      { from: "operator", to: "public_sector", what: "land price or rent (where the municipality owns the land) and building-permit fees" },
      { from: "operator", to: "public_sector", what: "property tax, every year" },
      { from: "operator", to: "public_sector", what: "electricity tax, to the state through the electricity bill" },
      { from: "operator", to: "public_sector", what: "corporate income tax, shared by the state and municipalities" },
    ],
    sources: [
      { label: "Kuntaliitto — selling and leasing plots as tools of municipal land policy", url: "https://www.kuntaliitto.fi/sites/default/files/media/file/Toimiva%2Byhdyskunta%2Bon%2Bkuntalaisen%2Barjen%2Bkulmakivi_Kuntaliitto_luottamushenkil%C3%B6t-compressed_1.pdf" },
      { label: "City of Hämeenlinna — building-control fees from 1.1.2025, under the Building Act (751/2023)", url: "https://www.hameenlinna.fi/rakennusvalvonnan_viranomaistehtavista_seka_muista_tehtavista_suoritettavat_maksut_1_1_2025__839992-1" },
      { label: "Vero.fi — Real estate tax: paid to the municipality where the property is", url: "https://www.vero.fi/en/individuals/property/real-estate-tax/" },
      { label: "Ministry of Finance — Business taxation: corporate tax shares of the state and municipalities (tax year 2024)", url: "https://vm.fi/en/business-taxation" },
      { label: "Ministry of Finance — Taxation of earned income: municipal tax", url: "https://vm.fi/en/taxation-of-earned-income" },
      { label: "Caruna — electricity tax is forwarded in full to the state (2026)", url: "https://caruna.fi/en/news/strategic-stockpile-fee-included-electricity-tax-will-increase-1-april-2026" },
      { label: "Vero.fi — Tax rates on electricity and certain fuels, 1.4.–31.12.2026", url: "https://www.vero.fi/en/businesses-and-corporations/taxes-and-charges/excise-taxation/sahkovero/Tax-rates-on-electricity-and-certain-fuels/" },
      { label: "Vero.fi — Sähkövero: data centres in class II until 30.6.2026, class I from 1.7.2026", url: "https://www.vero.fi/yritykset-ja-yhteisot/verot-ja-maksut/valmisteverotus/sahkovero/" },
      { label: "Finnish Government — state aid for data centres as ten-year tax relief, 5.12.2025", url: "https://valtioneuvosto.fi/en/-/ministerial-committee-on-economic-policy-decides-on-state-aid-for-data-centres-and-registration-obligation" },
      { label: "The Star (Xinhua) — Finland drops planned financial support for data centers, 2.9.2026", url: "https://www.thestar.com.my/news/world/2026/09/02/finland-drops-planned-financial-support-for-data-centers" },
    ] },
];

// Examples per stakeholder (R52/R53): well-known global companies and ones
// in Finland, each publicly verifiable (sources below). `dashboard` names the
// Daily signals sub-layers whose listed companies stand in for the global
// examples of that box (taken from the dashboard's config, not typed here;
// their short display names arrive with the display-name field after the R45
// merge). Finland is left empty where no credible Finnish example was found
// (cooling, equipment, storage). Customer examples prefer the customer's own
// source; a vendor's own announcement is labelled as such.
const EXAMPLES_REVIEWED = "10/2026";
const EXAMPLES = {
  operator: { dashboard: ["colocation"], finland: ["Telia (Helsinki)", "Verne (Helsinki, Pori, Tampere)", "Equinix (Helsinki)"],
    sources: [
      { label: "Helen — Telia's Helsinki data centre heats homes (2021)", url: "https://www.helen.fi/en/news/2021/konesalien-hukkalammosta-hiilineutraalia-kaukolampoa" },
      { label: "Verne — renewable diesel for the backup generators of its Finnish data centers (2024)", url: "https://www.verne.co/news/news-verne-switches-to-nestes-renewable-diesel-to-fuel-back-up-power-generators-at-its-finnish-data-centers" },
      { label: "Equinix — new data center in Helsinki (2018)", url: "https://investor.equinix.com/news-events/press-releases/detail/190/equinix-announces-build-of-new-data-center-in-helsinki" },
    ] },
  public_sector: { global: ["Loudoun County, Virginia (US)", "City of Stockholm"], finland: ["Hamina (Google)", "Espoo and Kirkkonummi (Microsoft)", "Mäntsälä (Nebius)"],
    sources: [
      { label: "Loudoun County — Data centers: tax revenues & county budget", url: "https://www.loudoun.gov/6409/Tax-Revenues-County-Budget" },
      { label: "Stockholm Data Parks — the city's partnership with Stockholm Exergi and others", url: "https://stockholmdataparks.com/" },
      { label: "DCD — Google's Hamina site", url: "https://www.datacenterdynamics.com/en/news/google-invest-670m-to-build-second-facility-hamina-finland-/" },
      { label: "Microsoft — data center region in Finland (Espoo and Kirkkonummi), 2022", url: "https://news.microsoft.com/europe/2022/03/17/microsoft-announces-intent-to-build-a-new-datacenter-region-in-finland-accelerating-sustainable-digital-transformation-and-enabling-large-scale-carbon-free-district-heating/" },
      { label: "Data Centre Review — Nebius to triple capacity at its Mäntsälä site", url: "https://datacentrereview.com/?p=82941" },
    ] },
  construction: { global: ["Turner Construction", "DPR Construction", "HITT Contracting"], finland: ["Caverion"],
    sources: [
      { label: "BD+C — Top data center construction firms for 2025", url: "https://www.bdcnetwork.com/giants-400/news/55321777/top-data-center-construction-firms-for-2025" },
      { label: "Caverion — contract for the expansion of a data centre in Finland (Nebius, Mäntsälä), 2025", url: "https://www.caverion.com/newsroom/releases/2025/caverion-strengthens-its-position-as-key-partner-in-major-infrastructure-investments-in-europe--secures-a-large-contract-related-to-the-expansion-of-a-state-of-the-art-data-centre-in-finland/" },
    ] },
  energy_gen: { global: ["Neoen", "wpd"], finland: ["Suomen Hyötytuuli"],
    sources: [
      { label: "Energy Digital — Google's wind power agreements in Finland (Neoen, wpd, CPC), 2018", url: "https://www.energydigital.com/renewable-energy/google-signs-agreements-190mw-wind-projects-finland" },
      { label: "Suomen Hyötytuuli — long-term PPA with Google", url: "https://hyotytuuli.fi/en//ajankohtaista" },
    ] },
  tso: { global: ["TenneT", "National Grid"], finland: ["Fingrid"],
    sources: [
      { label: "TenneT", url: "https://www.tennet.eu/" }, { label: "National Grid", url: "https://www.nationalgrid.com/" },
      { label: "Fingrid", url: "https://www.fingrid.fi/en/" },
    ] },
  dso: { global: ["E.ON", "Enel"], finland: ["Caruna", "Elenia"],
    sources: [
      { label: "E.ON", url: "https://www.eon.com/" }, { label: "Enel", url: "https://www.enel.com/" },
      { label: "Caruna", url: "https://caruna.fi/en" }, { label: "Elenia", url: "https://www.elenia.fi/en" },
    ] },
  district_heating: { global: ["Stockholm Exergi", "Fjernvarme Fyn"], finland: ["Fortum (Espoo)", "Helen (Helsinki)"],
    sources: [
      { label: "Stockholm Data Parks — data center heat for Stockholm Exergi's network", url: "https://stockholmdataparks.com/" },
      { label: "Ramboll — Meta's surplus heat to Fjernvarme Fyn's district heating, Odense", url: "https://www.ramboll.com/projects/energy/meta-surplus-heat-to-district-heating" },
      { label: "Fortum — heat production at two data centre sites in Finland (2026)", url: "https://www.fortum.com/en/media/2026/05/fortum-has-started-heat-production-two-large-data-centre-sites-finland" },
      { label: "Helen — district heat from Telia's data centre (2021)", url: "https://www.helen.fi/en/news/2021/konesalien-hukkalammosta-hiilineutraalia-kaukolampoa" },
    ] },
  cooling: { dashboard: ["cooling"], finland: [], sources: [] },
  backup_power: { global: ["Caterpillar", "Cummins"], finland: ["Neste"],
    sources: [
      { label: "Caterpillar", url: "https://www.cat.com/" }, { label: "Cummins", url: "https://www.cummins.com/" },
      { label: "Neste — renewable diesel for Verne's backup generators in Finland (2024)", url: "https://neste.com/news/neste-my-renewable-diesel-to-power-verne-data-centers-back-up-generators-in-finland" },
    ] },
  equipment: { dashboard: ["compute"], finland: [], sources: [] },
  capital: { global: ["Blackstone", "Brookfield", "KKR"], finland: ["Varma", "Tesi"],
    sources: [
      { label: "Data Center Frontier — Blackstone acquires QTS (2021)", url: "https://www.datacenterfrontier.com/qts-acquired-by-blackstone-in-blockbuster-data-center-ma-deal" },
      { label: "AXA IM Alts — sale of Data4 to Brookfield Infrastructure (2023)", url: "https://alts.axa-im.com/media-centre/axa-im-alts-agrees-sale-data4-european-leading-data-centre-platform-brookfield-infrastructure" },
      { label: "KKR and GIP complete the acquisition of CyrusOne (2022)", url: "https://www.streetinsider.com/Business+Wire/KKR+and+GIP+Complete+Acquisition+of+CyrusOne/19826569.html" },
      { label: "The Next Web — Verda's 2026 funding round (Varma and Tesi among the investors)", url: "https://thenextweb.com/news/verda-117m-funding-lifeline-ventures-ai-cloud" },
    ] },
  hyperscaler: { global: ["Microsoft", "Google", "Amazon (AWS)"], finland: ["Google (Hamina)", "Microsoft (Espoo and Kirkkonummi)"],
    sources: [
      { label: "DCD — Google's Hamina site", url: "https://www.datacenterdynamics.com/en/news/google-invest-670m-to-build-second-facility-hamina-finland-/" },
      { label: "Microsoft — data center region in Finland, 2022", url: "https://news.microsoft.com/europe/2022/03/17/microsoft-announces-intent-to-build-a-new-datacenter-region-in-finland-accelerating-sustainable-digital-transformation-and-enabling-large-scale-carbon-free-district-heating/" },
    ] },
  network: { dashboard: ["networking", "optical"], finland: ["Cinia", "Nokia"],
    sources: [
      { label: "Cinia — the C-Lion1 submarine cable, Helsinki–Rostock", url: "https://www.cinia.fi/en/news/c-lion1-submarine-cable-fully-restored" },
      { label: "Nokia — data center networking", url: "https://www.nokia.com/newsroom/nokia-announces-generational-step-in-data-center-networking-new-os-and-tools-give-cloud-builders-unprecedented-ability-to-adapt-automate-and-scale/" },
    ] },
  storage: { global: ["NetApp", "Pure Storage", "Dell Technologies"], finland: [],
    sources: [
      { label: "NetApp", url: "https://www.netapp.com/" }, { label: "Pure Storage", url: "https://www.purestorage.com/" },
      { label: "Dell Technologies", url: "https://www.dell.com/" },
    ] },
  enterprise: { global: ["Netflix (on AWS)", "Spotify (on Google Cloud)"], finland: ["Säästöpankkiryhmä (on Microsoft Azure)"],
    sources: [
      { label: "Netflix — completing the Netflix cloud migration (2016)", url: "https://about.netflix.com/en/news/completing-the-netflix-cloud-migration" },
      { label: "Spotify Engineering — a history of Spotify's journey to the cloud (2019)", url: "https://engineering.atspotify.com/2019/12/views-from-the-cloud-a-history-of-spotifys-journey-to-the-cloud-part-1-2" },
      { label: "Microsoft (vendor reference) — Säästöpankkiryhmä and Microsoft, 15.8.2023", url: "https://news.microsoft.com/fi-fi/2023/08/15/saastopankkiryhma-rakentaa-kestavaa-tulevaisuutta-yhdessa-microsoftin-kanssa/" },
    ] },
  neocloud: { global: ["CoreWeave", "Nebius", "Lambda"], finland: ["Nebius (Mäntsälä)", "Verda (Helsinki)"],
    sources: [
      { label: "Analysys Mason — Neocloud GPU-as-a-service providers", url: "https://www.analysysmason.com/research/content/reports/neocloud-gpuaas-studies-rma16/" },
      { label: "Data Centre Review — Nebius to triple capacity at its Mäntsälä site", url: "https://datacentrereview.com/?p=82941" },
      { label: "Verda — DataCrunch is changing its name to Verda", url: "https://verda.com/blog/datacrunch-is-changing-its-name-to-verda" },
    ] },
};

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

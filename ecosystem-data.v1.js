// ecosystem-data.v1.js — single source of truth for the interactive Data
// Center Ecosystem map. Diagram arrows, the legend, and the side panel are
// all generated from this file, so they can't drift apart the way the
// static poster image's arrow colors drifted from its own legend.
//
// Versioned filename: any future content edit gets a new suffix (v2, v3...)
// rather than reusing this one, so browser/CDN caches can't silently serve
// stale content (the same lesson as the poster image rename).
//
// Accuracy (CLAUDE.md): general mechanisms below are not independently
// cited. The one named real-world example (Fortum/Microsoft, Espoo &
// Kirkkonummi) is sourced — see CASE_STUDY.sources and the explanation
// section in ecosystem.html, which cites the same sources. DSO and
// district-heating stakeholder descriptions deliberately say "e.g." before
// naming a company — Finland has many DSOs and district heating companies,
// so naming one as *the* operator would be inaccurate.

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
    description: "Runs the facility itself — as a colocation provider (rents space, power, and cooling to many customers), a hyperscaler operating its own site, or a third-party operator managing it on behalf of an owner." },

  { id: "public_sector", name: "Public Sector / Municipality", x: 350, y: 80,
    description: "Grants zoning, land use, and permits, and coordinates infrastructure access for new data center developments." },
  { id: "construction", name: "Construction & Real Estate", x: 650, y: 80,
    description: "Land and site developers, construction contractors, and permitting specialists who build the physical facility." },

  { id: "energy_gen", name: "Energy & Power Generation", x: 100, y: 140,
    description: "Producers supplying the grid — renewables (wind, solar, hydro), nuclear, gas, and other sources — that a data center's power ultimately comes from." },
  { id: "tso", name: "Transmission (TSO)", x: 100, y: 230,
    description: "Operates the national high-voltage transmission grid and substations. In Finland: Fingrid." },
  { id: "dso", name: "Distribution (DSO)", x: 100, y: 320,
    description: "Operates regional and local electricity distribution networks, separate from the national transmission grid — e.g. Caruna in Finland." },
  { id: "district_heating", name: "District Heating / Energy Recovery", x: 100, y: 410,
    description: "Utilities capturing a data center's waste heat and distributing it as district heating (kaukolämpö) to homes, offices, and industrial users — e.g. Fortum in Finland." },
  { id: "cooling", name: "Cooling & HVAC Suppliers", x: 100, y: 500,
    description: "Suppliers of chillers, cooling systems, liquid cooling, and heat rejection equipment." },
  { id: "backup_power", name: "Backup Power & Fuel", x: 100, y: 590,
    description: "Suppliers of generators, fuel, UPS systems, and backup power distribution." },

  { id: "equipment", name: "Equipment & Technology Suppliers", x: 900, y: 140,
    description: "Suppliers of compute (GPU/ASIC) hardware and power/electrical equipment for the facility." },
  { id: "capital", name: "Capital & Finance", x: 900, y: 230,
    description: "Infrastructure funds, data center REITs, lenders, and equity partners financing construction and operation." },
  { id: "hyperscaler", name: "Hyperscaler / Cloud", x: 900, y: 320,
    description: "Large cloud platforms — Microsoft, Google, Amazon, and similar — buying or operating compute capacity, serving their own external customers." },

  { id: "network", name: "Network & Connectivity", x: 650, y: 620,
    description: "Suppliers of fiber, cabling, switches, routers, optical transport, and interconnection." },
  { id: "storage", name: "Storage Providers", x: 500, y: 650,
    description: "Suppliers of storage arrays, data protection, and backup & recovery systems." },
  { id: "enterprise", name: "Enterprise & End Users", x: 350, y: 620,
    description: "Businesses, developers, and consumers — the end users of the compute, storage, and connectivity a data center provides." },
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

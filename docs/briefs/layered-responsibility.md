# Layered responsibility view: brief for the data center business models page

Version 2, 20 October 2026. Supersedes the earlier chat version. Changes from version 1 are listed at the end.

## What we are adding

A new section on the business models hub page, placed ABOVE the existing comparison table (which tells the story through the fictional AI Oy). This section is GENERIC, not about AI Oy. It shows what a data center consists of and what a company handles itself and what it buys in each of the five models.

Why above the table: it moves from general to specific. Readers first understand the layers and who handles them, which makes the table rows ("Kerrokset", "Kuka kantaa riskin") easier to follow. The illustration also works as a visual entry point for a broad audience that does not know the industry.

Section title (FI): "Mitä yritys hoitaa itse ja mitä se ostaa" = "What a company handles itself and what it buys"

Bridge sentence placed between this section and the comparison table (FI): "Yllä rakenne yleisesti. Alla samat mallit kuvitteellisen AI Oy:n kasvupolkuna: miksi yritys siirtyy mallista toiseen ja mitä se ostaa, sitoo ja riskeeraa." = "Above, the structure in general. Below, the same models as the growth path of the fictional AI Oy: why a company moves from one model to the next, and what it buys, commits to and puts at risk."

## Core message (most important design constraint)

The full infrastructure stack exists in EVERY model. Even in the public cloud someone owns the building, the transformer and the backup generators. What changes between models is only how much of the stack the company handles itself. The iceberg is always the same size; the company's share grows downwards. Do NOT depict this as a pyramid where lower stages "have more elements". Show the full stack in every model and highlight the company's own share.

## Naming rules

- The company is labelled "Itse" (= itself), defined once as "Itse = yritys, joka tarvitsee laskentakapasiteettia" (a company that needs compute capacity). Do not use "asiakas" (customer): in the own data center model the company is the owner, not anyone's customer.
- Never use "tarjoaja"/"palveluntarjoaja" (provider) as a role name. Name the counterparty in every model: CSP, GPU-pilvi, colocation-operaattori, datakeskusoperaattori.
- The rule applies to the whole business models site, not only to this section. Update the live hub terms note that currently reads "riski on palveluntarjoajalla (operaattorilla tai pilvipalveluntarjoajalla)" to "riski on vastapuolella (CSP:llä, GPU-pilvellä tai operaattorilla)", so the page does not contradict itself.
- Columns and tabs use model names, not "vaihe 1–5" (stage refers to AI Oy's path): 1 Julkinen pilvi (public cloud), 2 GPU-pilvi, 3 Retail-colocation, 4 Wholesale-colocation, 5 Oma datakeskus. Same order as the table below.
- Established English terms (CSP = cloud service provider, colocation, turnkey, powered shell, demarc) are kept and explained briefly in Finnish in the legend.
- No product names (e.g. no H100/B200).

## Part A: the illustrated stack

### Build approach

(Updated 20 October 2026, ledger R61: the image replaces the drawn SVG artwork.)

The stack is the image docs/briefs/datakeskus-kerrokset-original.png, which already has the six levels in the right order. It is converted to WebP and self-hosted in the explainer's assets (business-models/assets/datakeskus-kerrokset.webp, 1672 x 941 px), and it is frozen: nothing that carries meaning is baked into it.

An SVG overlay with the same viewBox as the image's pixel size (0 0 1672 941) carries everything that means something: the zones, the highlights, the labels, the demarc line in the gaps between slabs, the connection-point marker, the waste-heat hotspot and the clickable zone buttons. Because the overlay uses the image's own pixel coordinates, it can't drift out of alignment at any display size.

- The zone polygons are measured on the final WebP file and stored in the data file (business-models/assets/kerrokset-data.js), with the demarc gaps and the marker positions. If the image ever changes, every coordinate is measured again.
- Z4 is drawn around the caged racks only: the free-standing white units on that floor read as in-row cooling, and cooling stays in row 8 (Z5).
- The connection-point marker sits where the lines from the pylons reach the substation fence; the waste-heat hotspot is on the red and blue district heating pipe toward the town.
- The image has Finnish alt text; zones and markers are real buttons with text labels.

Visual reference for richness: a ChatGPT mockup in a realistic isometric cutaway style (snowy Finnish landscape, slabs between floors, model tabs on top, side panel on the right).

### Six zones, top to bottom

- Z1 Sovellukset, data ja ohjelmistot: abstract translucent panels / cloud
- Z2 Ohjelmistoalusta: thin grid slab, no equipment
- Z3 Palvelimet ja verkko: servers, storage, network switches
- Z4 Palvelinsali: rows of racks in cages and suites, power to racks
- Z5 Rakennuksen tekniikka: cooling units, UPS, backup generators
- Z6 Kiinteistö ja liittymä: land plot, building shell (rakennus, runko), substation and transformers, grid connection, district heating pipe leading towards a town

The server hall (Z4) MUST be above building systems (Z5); otherwise the wholesale turnkey boundary cannot be drawn as a single line.

### Zone ↔ staircase row mapping

Z1 = rows 1–3 | Z2 = row 4 | Z3 = rows 5–6 | Z4 = row 7 | Z5 = rows 8–10 | Z6 = rows 11–14

### Responsibility line (demarc) per model

- Julkinen pilvi: typically between Z1 and Z2 (IaaS: the company manages the operating system). Shown as a range: it moves up into Z1 for PaaS and SaaS.
- GPU-pilvi: typically between Z2 and Z3 (dedicated or bare-metal clusters, where the company often runs its own orchestration). Shown as a range: it moves up to Z1/Z2 for managed or virtualised GPU services.
- Retail-colocation: between Z3 and Z4
- Wholesale-colocation: turnkey between Z4 and Z5; powered shell between Z5 and Z6 (two named lines). The building shell in Z6 is what the landlord provides in powered shell.
- Oma datakeskus: no line inside the company's stack.

Cloud lines are marked "tyypillisesti" (typically). The side panel for both cloud models says (FI): "Raja riippuu ostetusta palvelusta: IaaS:ssä yritys hallitsee käyttöjärjestelmän, PaaS- ja SaaS-palveluissa vastapuoli hoitaa enemmän (shared responsibility model)."

Grid connection point: a small fixed marker at the outer edge of Z6, the same in every model, own data center included. The network company's responsibility ends at the connection point; electricity itself is bought separately (row 13). Label (FI): "Liittymispiste: verkkoyhtiön vastuu päättyy tähän."

Legend (FI): "Vastuuraja (demarc): kohta, jossa vastapuolen vastuu päättyy ja yrityksen oma vastuu alkaa."

### Interaction

- Model tabs above the stack (the five models).
- Selecting a model highlights the zones the company handles itself and shows the counterparty name on the others; the orange dashed demarc moves to the right gap with a smooth animation.
- Clicking a zone opens a side panel on the right: the zone's elements and who handles each in the selected model (data from the cell table in Part B).
- Separate hotspot on the district heating pipe (not a responsibility zone): waste heat is sold to the district heating network by the data center owner or operator. Examples: the Mäntsälä data center has sold heat to district heating since 2015 (built by Yandex, now Nebius); the Microsoft–Fortum agreement on heat from future data centers. Use the same Fortum source and wording as the ecosystem page so the two pages do not drift apart. Link to "Hukkalämmön myynti" on the specialised models page.
- Mobile: stack on top, zone list below.

### Accessibility

- Respect prefers-reduced-motion: the demarc line jumps instead of sliding, highlights change without transitions.
- Tabs follow the WAI-ARIA tabs pattern (arrow keys, aria-selected).
- Zones are keyboard-focusable buttons with descriptive labels, e.g. "Palvelinsali: colocation-operaattori hoitaa" for the selected model.
- The side panel is announced to screen readers (aria-live="polite").
- Colour is never the only carrier: "Itse" and counterparty names appear as text; fills differ in lightness, not hue alone.

## Part B: the responsibility staircase (directly below the stack)

To keep the hub page an overview, the staircase grid is collapsed by default behind a control (FI: "Näytä kaikki mallit rinnakkain" = "Show all models side by side"). The tabs and side panel already show the same information one model at a time; the grid opens for readers who want the full comparison.

A grid with the five models as columns and 14 elements as rows, grouped into five layers. "Itse" cells use a strong, solid fill so the staircase shape emerges from left to right; counterparty cells use a light fill and the counterparty name. The name always appears as text, not only as colour. Adjacent identical cells in a column may merge. Hovering or focusing a row highlights the matching zone in the stack, and vice versa.

### Rows

SOVELLUKSET JA DATA
- 1 Sovellukset ja tekoälymallit
- 2 Data

ALUSTA
- 3 Käyttöjärjestelmä ja ohjelmistokirjastot
- 4 Virtualisointi ja klusterin hallinta

LAITTEET
- 5 Palvelimet ja tallennus
- 6 Verkkolaitteet

KONESALI
- 7 Räkit ja sähkönsyöttö räkkiin
- 8 Jäähdytys (ilma tai neste)
- 9 UPS ja varavoima
- 10 Kulunvalvonta ja fyysinen turvallisuus

KIINTEISTÖ JA ENERGIA
- 11 Tontti ja rakennus
- 12 Sähköliittymä ja muuntamo
- 13 Sähkön hankinta
- 14 Luvat ja kaava

### Cells (use exactly)

- Julkinen pilvi: 1–2 Itse · 3 Jaettu: IaaS itse, PaaS CSP · 4–14 CSP
- GPU-pilvi: 1–3 Itse · 4 Jaettu sopimuksen mukaan · 5–14 GPU-pilvi (footnote: the GPU cloud may sit in its own or a colocation operator's data center)
- Retail-colocation: 1–6 Itse · 7–14 Colocation-operaattori (footnote: power is usually passed through to the company)
- Wholesale-colocation: 1–7 Itse · 8–10 "Turnkey: operaattori · Powered shell: itse" · 11–12 Datakeskusoperaattori · 13 Itse tai läpilaskutettuna · 14 Datakeskusoperaattori
- Oma datakeskus: 1–14 Itse

Footnote on row 12 for all models (FI): "Verkkoyhtiö vastaa verkosta liittymispisteeseen asti."

### Mandatory note under the staircase (FI)

"Kerrokset eivät näytä kaikkia eroja. Julkisen pilven ja GPU-pilven ero on ennen kaikkea sitoumuksessa: GPU-pilvessä kapasiteetti varataan omaan käyttöön monivuotisella sopimuksella. Retail- ja wholesale-colocationin ero on mittakaavassa ja sopimuksessa: wholesale on kokonainen sali tai rakennus 5–15 vuoden vuokrasopimuksella. Pilvimalleissa vastuuraja riippuu myös ostetusta palvelusta."

## Relationship to the existing table

The comparison table below this section has a small "Kerrokset" bar row. Either remove it or turn it into a link back to this section, so the same information is not shown twice at different levels of detail.

## Style

Light, calm editorial look consistent with the rest of the business models pages (not the dark dashboard style). Read mainly at a desk; the phone is secondary, but the section must remain usable on mobile.

## Storage

Keep this brief in the repo outside the deployed folder, e.g. docs/briefs/layered-responsibility.md (the deploy copies the whole business-models/ folder to the live site).

## Changes from version 1

- Cloud demarcs shown as typical positions with a range; side panel text on the shared responsibility model.
- Building shell added explicitly to Z6 (needed for powered shell).
- Fixed grid connection point marker in every model, plus a row 12 footnote.
- Naming rule extended to the whole site; live hub note to be updated.
- Mäntsälä fact corrected (heat since 2015 belongs to the site, built by Yandex, now Nebius); Microsoft–Fortum aligned with the ecosystem page's source.
- Vector SVG is now the primary build approach; a raster AI image only as optional decoration.
- Accessibility section added (reduced motion, keyboard, screen reader).

## Change after version 2

- 20 October 2026 (ledger R61): the image datakeskus-kerrokset-original.png is the stack; the SVG is an overlay on it with the image's pixel size as its viewBox (see Build approach).

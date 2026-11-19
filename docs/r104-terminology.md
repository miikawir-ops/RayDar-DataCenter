# English explainer: terminology (ledger R104)

The Finnish term → the English term chosen for the English business-models pages
(business-models/en/). Batches 2 and 3 follow this list; any deviation is named in
that batch's report. Spelling is American, as on the English dashboard and
ecosystem pages ("data center", "color", "utilization", "specialized").

## Names and fixed choices

| Finnish | English | Note |
|---|---|---|
| AI Oy | AI Ltd | Fictional, as on the Finnish pages ("AI Ltd is fictional; the other companies are real.") |
| Datakeskusten liiketoimintamallit | Data center business models | Page and site title |
| TIEDOT TARKISTETTU 9/2026 | CONTENT REVIEWED 9/2026 | Same date as the Finnish page |
| tarkistettu 10/2026 (source notes) | reviewed 10/2026 | Dates kept |
| Lähteet | Sources | |
| Tilanne syyskuu 2026 | As of September 2026 | |
| Fingrid, Caruna, Fortum, Helen, Nebius, … | unchanged | Finnish proper nouns kept |
| kaukolämpö | district heating (kaukolämpö) | Finnish word once per page, at first use |
| kantaverkko | transmission grid (kantaverkko) | Finnish word once, at first use |

## Header and footer (shared chrome)

| Finnish | English |
|---|---|
| Kasvupolku | Growth path |
| AI Oy:n kasvupolku (screen readers) | AI Ltd's growth path |
| Vaihe 1 … 5 | Stage 1 … 5 |
| Sivut | Pages |
| One pager · Arvoketju · Rahoitusmallit · Erikoistuneet mallit · Miksi Suomi · Sanasto | One pager · Value chain · Financing models · Specialized models · Why Finland · Glossary |
| Kieli (switch, screen readers) | Language |
| Ei sijoitusneuvontaa · Opetuskäyttöön tarkoitettua taustatietoa | Not investment advice · Background information for educational use |
| Osa RayDar-perhettä | Part of the RayDar family |
| Henkilökohtainen projekti · Miika Ray Wires | Personal project · Miika Ray Wires |

## The five models (stage names)

| Finnish | English |
|---|---|
| Julkinen pilvi | Public cloud |
| GPU-pilvi | GPU cloud (glossary alt: neocloud) |
| Retail-colocation | Retail colocation |
| Wholesale-colocation | Wholesale colocation |
| Oma datakeskus | Own data center |

## Layered view and responsibility table

| Finnish | English | Note |
|---|---|---|
| Itse | In-house | The company that needs the capacity |
| Vastapuoli | Counterparty | |
| Vastuuraja (demarc) | Responsibility line (demarc) | |
| Jaettu tai riippuu palvelusta tai sopimuksesta | Shared, or depends on the service or contract | |
| Pilvipalveluyhtiö (CSP) | cloud service provider (CSP) | |
| Colocation-operaattori | Colocation operator | |
| Datakeskusoperaattori | Data center operator | |
| Verkkoyhtiö | Grid company | Fingrid (TSO) or a distribution company such as Caruna (DSO) |
| Liittymispiste | Grid connection point | |
| Sähköliittymä ja muuntamo | Grid connection and substation | |
| Sähkön hankinta | Electricity procurement | |
| läpilaskutettuna | passed through (pass-through) | |
| Konesali / palvelinsali | Data hall | |
| Räkki | Rack | |
| Rakennuksen tekniikka | Building systems | Cooling, UPS, backup power, access control |
| Kiinteistö ja liittymä | Site and grid connection | |
| Varavoima | Backup power | |
| Kulunvalvonta | Access control | |
| Kahdennus | Redundancy | |
| Hukkalämpö | Waste heat | |
| hallittu palvelu | managed service | |

## The growth-path matrix

| Finnish | English |
|---|---|
| RAKENNUKSEN OMISTAA | BUILDING OWNED BY |
| AI OY OSTAA | AI LTD BUYS |
| AI OY:N SITOUMUKSET | AI LTD'S COMMITMENTS |
| SOPIMUS · HINNOITTELU | CONTRACT · PRICING |
| SÄHKÖN MAKSAA | ELECTRICITY PAID BY |
| KUKA KANTAA RISKIN | WHO CARRIES THE RISK |
| KÄYTTÖASTE / LAITTEET | UTILIZATION / EQUIPMENT |
| VASTAPUOLEN TULOT | COUNTERPARTY REVENUE |
| MITTAKAAVA | SCALE |
| MIKSI TÄHÄN VAIHEESEEN | WHY THIS STAGE |
| TODELLISIA TOIMIJOITA | REAL-WORLD PLAYERS |
| Kiinteistösijoittaja | Real estate investor |
| varattu teho (€/kW) | reserved power (€/kW) |
| v (vuotta) | yrs |

## Commercial and financing terms

Kept as the industry writes them: colocation, retail/wholesale colocation, powered
shell, turnkey, PPA, hyperscaler, neocloud, TSO/DSO, take-or-pay, pass-through,
cross-connect, remote hands, build-to-suit, sale-leaseback, REIT, SPV, ABS, DDTL.

| Finnish | English |
|---|---|
| Hyperskaalaaja | Hyperscaler |
| Käyttöaste(riski) | Utilization (risk) |
| Sitoumus | Commitment |
| Vuokrasopimus / vuokravastuu | Lease / lease obligation |
| Infrarahasto | Infrastructure fund |
| Projektirahoitus | Project finance |
| Joukkovelkakirja / vihreä joukkovelkakirja | Bond / green bond |
| Vaihtovelkakirja | Convertible note |
| Emoyhtiön takaus | Parent company guarantee |
| Jäännösarvo(takuu) | Residual value (guarantee) |
| Jälleenrahoitus | Refinancing |
| Taseen ulkopuolinen rahoitus | Off-balance-sheet financing |
| Vastapuoliriski | Counterparty risk |
| Yhdysliikennepiste | Internet exchange (IX) |
| Verkkoekosysteemi | Network ecosystem |
| Kantaverkkoliittymä | Transmission grid connection |
| Sähköveroluokka I / II | Electricity tax class I / II |
| veronpalautustuki (kymmenvuotinen) | ten-year tax-relief aid (the Finnish Government's English release calls it "tax relief") |

## Glossary (business-models/assets/glossary-en.js)

75 terms, the same keys as the Finnish file. Rebuilt, not translated: entries headed
by a Finnish word with an English alt become one English entry (Räkki / rack → Rack);
alts that only gave the Finnish name are dropped (ristikytkentä, datakeskuskehittäjä,
varattu kapasiteetti; "myös reserved" becomes "also reserved"). No two Finnish entries
turned out to be the same concept in English, so nothing merged; the Finnish file
already had one entry per concept (PPA, for example, is one entry with "power purchase
agreement" as its alt). Sorted by the English term.

# RayDar Data Center — Project Specification & Agent Rules

> Source of truth for the Data Center sub-agent. Claude Code reads this before
> making changes. Two parts: (A) inherited RayDar-family principles that keep this
> consistent with the parent AI value chain dashboard, and (B) Data-Center-specific
> spec. When in doubt, follow this document and match the parent's conventions.

---

# PART A — INHERITED RAYDAR-FAMILY PRINCIPLES

These are non-negotiable. They make this a genuine RayDar product, not a separate tool.
They are copied in spirit from the parent AI value chain agent.

## A1. Core identity

- **Brand:** Part of the RayDar family (RayDar, RayDar Vice, Quantum RayDar, RayDar Data Center).
- **Purpose:** Identify bottlenecks and emerging opportunities in the data center
  infrastructure value chain, for investors and curious observers alike.
- **Voice:** Honest, signal-focused, never hype. Surfaces genuine progress vs
  narrative-driven price moves.

## A2. Scoring philosophy (inherited)

- Bottleneck-focused: find where supply can't meet demand before the market prices it.
- Three signal categories, same as parent:
  - **Fundamentals** — revenue growth acceleration, margin expansion, pricing power
  - **Constraint signal** — news velocity, capex, supply/demand pressure
  - **Smart money** — volume-price confirmation, analyst clusters, short interest
- **Fundamental override:** if revenue growth is decelerating, a layer/company cannot
  be Red regardless of price momentum. Fundamentals always take priority.
- **Market-cap weighting:** layer/sub-layer scores are market-cap weighted composites,
  never driven by a single small ticker inflating the signal.
- **Multi-day color confirmation:** colors require confirmation across runs to prevent
  single-day noise from flipping the signal. Extreme signals may bypass confirmation.

## A3. Color system (identical to parent)

```
Red    (Hot)      — current bottleneck, supply can't meet demand, highest conviction
Orange (Emerging) — building momentum toward bottleneck, OR price ahead of fundamentals
Green  (Neutral)  — stable, healthy, no constraint pressure
Blue   (Cooling)  — previously hot, constraint easing, growth decelerating
```

Company ratings A/B/C/D with forecast arrows (↑ B→A buy, → stable, ↓ A→C warning),
identical to parent.

## A4. Investor-protection rules (inherited)

- **Hype divergence flag:** price ran up without fundamental/constraint backing → warn.
- **Narrative ahead of fundamentals:** news active but revenue not confirming → flag.
- **Not financial advice:** provide factual signals and analysis, never recommendations.
- **Data honesty:** mark data-backed vs estimated signals. Never fabricate. Quarterly
  financials may be up to 90 days old — always disclosed.

## A5. Visual design (match parent for family consistency)

- Dark "intelligence" hero: gradient `#08081A → #0C1A3A → #1A0830 → #0A0818`, laser
  beam at top, gradient tagline.
- White signal cards on dark navy body gradient.
- Macro/context cards, chain status bar, scrolling ticker band, heat trail — same
  components and color language as parent.
- Footer carries RayDar family branding and cross-links.

## A6. Technical architecture (reuse from parent)

```
fetch_market.py   — data pipeline (adapt tickers, keywords, ADD capex tracking)
score_engine.py   — reuse three-signal model, adapt weights per Part B
main.py           — pipeline + market-cap weighted aggregation (reusable)
render.py         — dashboard HTML, match parent's visual system
backtest.py       — signal quality tracking (reuse)
GitHub Actions    — deploy to GitHub Pages
index.html        — REQUIRED at repo root so the bare URL works (lesson from Vice)
```

News scoring must be **layer-filtered** — a ticker's headlines only count for its own
sub-layer, never cross-contaminate (critical lesson from the parent build).

---

# PART B — DATA CENTER SPECIFIC

## B1. What this agent does that the parent cannot

The parent collapses VRT, ANET, EQIX, SMCI, CSCO, CIEN into ONE "Data center" score.
That loses more information than any other layer — these are wildly different businesses.
This sub-agent breaks the layer into its real sub-components and adds a capex signal
the parent has no room for.

## B2. Sub-layer structure (score each as a mini-bottleneck)

```
Cooling          — VRT — the liquid cooling transition (biggest structural shift)
Networking       — ANET, CSCO — switch silicon, Ultra Ethernet
Optical          — CIEN, LITE, COHR, GLW — the 800G → 1.6T bandwidth race
Compute assembly — SMCI, DELL, HPE — server integration
Colocation       — EQIX, DLR — physical data center real estate
```

Each sub-layer gets its own Red/Orange/Green/Blue score. The dashboard shows which
PART of the data center buildout is most constrained right now (currently: optical
1.6T transition and liquid cooling are the hot sub-bottlenecks).

## B3. FLAGSHIP SIGNAL — Hyperscaler capex → supplier beneficiary mapping

This is the primary NEW signal and the reason the sub-agent exists.

**Concept:** Every dollar of AI capex flows through data center infrastructure. When a
hyperscaler raises capex guidance, that money reaches specific suppliers over the
following quarters — BEFORE it shows up in supplier revenue. Tracking this lag is the
"accumulation signal" for this layer.

```
Track hyperscaler capex (guidance + actuals): MSFT, GOOGL, AMZN, META
  ↓
Aggregate capex trend accelerating? → whole data center layer is a tailwind (top signal)
  ↓
Map capex to beneficiary sub-layers:
  - More GPU clusters      → cooling (VRT), compute (SMCI)
  - More interconnect      → networking (ANET), optical (CIEN, LITE)
  - More facilities        → colocation (EQIX, DLR)
  ↓
Surface: which suppliers benefit from the latest capex cycle, before revenue confirms
```

Top-level dashboard signal: **aggregate hyperscaler capex direction** (accelerating /
stable / decelerating) as the single most important read for the whole layer.

## B4. Boundary with the parent's Energy layer (avoid duplication)

```
This agent owns everything INSIDE the data center building:
  cooling, compute, networking, optical, power distribution (PDUs, UPS)

The parent's Energy layer owns everything UP TO the building:
  generation, grid, transmission, substations
```

Overlap zone (power/thermal at the building edge): this agent covers power
DISTRIBUTION inside; energy layer covers power DELIVERY to the site. State this
explicitly in any power-related signal to avoid double-counting.

## B5. Ticker universe

```
CORE (in parent):     VRT, ANET, EQIX, SMCI, CSCO, CIEN
ADDED (sub-layer depth): LITE (Lumentum), COHR (Coherent), GLW (Corning),
                         DELL, HPE, DLR (Digital Realty)
CAPEX SOURCES (context, not scored as suppliers): MSFT, GOOGL, AMZN, META
```

## B6. Update frequency

```
Daily light run  — price + news, keeps stock-signal layer fresh
Weekly deep run  — capex mapping + sub-layer bottleneck analysis (changes slowly)
```

Start daily-only if simpler; add the weekly deep layer once the core works.

## B7. Link from parent

The parent dashboard's "Data center & bandwidth" layer box links directly to this
sub-agent site. Implementation on the PARENT side (small, low-coupling):

- Make the Data center layer box a clickable link (or add a small "↗ deep dive" affordance).
- Opens this standalone site in a new tab.
- The sub-agent remains fully standalone — own pipeline, own deploy, own data.
- No shared state, no embedding. Just an outbound link, like RayDar → RayDar Vice.

## B8. Success criteria

The sub-agent succeeds if it:
- Shows which sub-layer (cooling/networking/optical/compute/colo) is the current
  bottleneck — granularity the parent can't provide.
- Reads aggregate hyperscaler capex direction as a top-level tailwind/headwind signal.
- Maps a capex cycle to beneficiary suppliers before revenue confirms it.
- Stays visually and behaviourally consistent with the RayDar family.
- Is something you actually open weekly. If not, the parent was already enough.

---

# PART C — OPEN DECISIONS (resolve before/while building)

1. **Capex data sourcing:** hyperscaler capex comes from earnings reports and guidance.
   Test whether it's cleanly parseable (yfinance cash-flow statements give capex actuals;
   guidance needs press-release/transcript parsing). If guidance is too manual initially,
   start with capex ACTUALS from cash-flow data and add guidance later.

2. **Sub-layer market-cap weighting:** some sub-layers have one dominant ticker (Cooling
   = VRT). Decide how to score a single-company sub-layer fairly vs multi-company ones.

3. **Daily-only vs daily+weekly:** start simple (daily-only) or build the two-tier
   cadence from the start. Recommend starting daily-only, add weekly deep once stable.
PART D — REFERENCE IMPLEMENTATION (reuse the parent's proven code)

The reference/ folder contains the WORKING, PROVEN implementation from the parent AI value chain agent (RayDar). This is the source of the RayDar DNA — not a description of it, but the actual battle-tested logic. Reuse it; do not rebuild from scratch.

reference/
  score_engine.py   — v3.1 bottleneck-focused scoring model (65/20/15 weights,
                       high-margin multiplier, fundamental override, macro multiplier,
                       A/B/C/D company ratings, hype detection)
  main.py           — pipeline orchestration + market-cap weighted layer scoring,
                       bottleneck leader boost, Red reality check, 3-day color
                       confirmation with instant-Red bypass
  fetch_market.py   — data pipeline with LAYER-FILTERED news scoring (ticker headlines
                       only count for their own layer — the fix for the cross-
                       contamination bug that made every layer score 10.0)
  render.py         — dashboard HTML: dark hero, laser beam, chain status bar, layer
                       cards with ratings/forecasts, expand panels with 52W position +
                       run rate, heat trail, radar section, visual design system
D1. How to reuse
score_engine.py — reuse the three-signal structure, the fundamental override, the macro multiplier, and the A/B/C/D rating logic AS-IS. Adapt only the weights and any data-center-specific signal (capex) per Part B. Keep the calibration philosophy.
main.py — reuse market-cap weighting, the Red reality check, and 3-day confirmation AS-IS. Adapt the layer aggregation to the sub-layer structure (Part B2).
fetch_market.py — reuse the layer-filtered news algorithm EXACTLY. This fix is non-negotiable (Part A6). Adapt tickers, keywords, and add capex data (Part B3).
render.py — reuse the visual system and component structure to stay visually consistent with the family (Part A5). Adapt content to the two-lens data-center view.
D2. How to adapt (not copy blindly)
Do NOT copy the parent's exact 7-layer AI structure. This agent uses the sub-layer structure in Part B2 (cooling / networking / optical / compute / colocation).
Do NOT copy the parent's ticker universe wholesale. Use Part B5.
The capex → beneficiary mapping (Part B3) is NEW — it has no parent equivalent. Build it fresh, but in the same code style and quality as the reference files.
D3. Rule

When implementing any core mechanic (scoring, weighting, news filtering, confirmation, color assignment), CHECK the reference implementation first and reuse its logic. Only diverge where Part B explicitly requires it. If you find yourself reinventing something the reference already solves, stop and reuse the reference instead.
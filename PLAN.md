# PLAN.md — Build order for RayDar Data Center

Agreed plan, not yet executed. Continue from here next session.
See CLAUDE.md and DATACENTER_RAYDAR_SPEC.md for full rules/spec.

## Decisions settled

1. **Capex signal = overlay only.** The hyperscaler capex trend (Part B3)
   is a top-level display badge + beneficiary mapping. It does NOT feed
   into score_engine.py's constraint score or change any weights/thresholds.
   The reused scoring engine stays untouched.

2. **Single-ticker sub-layers (Cooling = VRT) use the ticker's own score
   directly.** No separate weighting logic needed — market-cap weighting
   already degenerates correctly to N=1.

3. **Red reality check is skipped for single-ticker sub-layers.** The
   parent's "top-2 companies both C/D → downgrade" check needs 2+ tickers
   and doesn't apply when there's only one.

4. **Capex direction = single-quarter YoY snapshot, not trailing-4-quarter
   YoY.** This supersedes the "trailing-4Q vs single-YoY" framing entirely
   — trailing-4Q isn't a rejected option, it's **nonviable on this data
   source**: it needs 8 quarters (current 4Q window + prior-year 4Q
   window), and yfinance's free `quarterly_cashflow` caps at 7 quarters
   total (confirmed via `get_cashflow(freq='quarterly')` too — same 7
   columns, no way to get more). GOOGL only returns 5 quarters total;
   MSFT/AMZN/META return 6–7 with the oldest 1–2 NaN. None of the 4
   hyperscalers can fill a prior-year 4Q window. Do not reconsider
   trailing-4Q later without a different data source — the constraint is
   structural, not a tuning issue.

   **Method:** for each hyperscaler, compare the latest non-null quarter
   to the quarter exactly 4 positions back (same fiscal quarter, prior
   year) from `quarterly_cashflow`'s `Capital Expenditure` row (not
   `Net PPE Purchase And Sale` — that nets out disposal proceeds and is a
   different number for AMZN).

   - **No fallback to nearest-available quarter.** If the slot exactly
     4-back is NaN (or doesn't exist in the returned columns), that
     ticker is "insufficient data" for this run, full stop — do not
     substitute the nearest non-null quarter, that would silently weaken
     the seasonality control the whole method exists for. Consistent
     with the CLAUDE.md fetch-failure rule: a missing quarter is missing,
     not approximated.
   - **Don't drop an insufficient-data ticker from the aggregate
     silently.** Surface it (e.g. "3 of 4 hyperscalers reporting, AMZN
     insufficient data this run") — a 3-company aggregate direction is a
     materially different number from a 4-company one and must not look
     the same in the output.
   - **Show magnitude, not just the label.** Store and display the YoY %
     alongside accelerating/stable/decelerating, so a viewer can see when
     a single lumpy quarter is driving the classification rather than a
     genuine trend.
   - **Label thresholds are named constants in the config module (Part
     B2), not inline judgment calls in 5b.** E.g.
     `CAPEX_YOY_ACCELERATING_PCT` / `CAPEX_YOY_DECELERATING_PCT` — starting
     values still need picking (propose during 5b, sanity-check against
     4b's real fetched numbers, not guessed blind), but the mechanism must
     be a tunable constant, not a magic number buried in a conditional.

5. **News matching requires a context/topic keyword, not just a brand-name
   mention — and context vocabulary must include plain bottleneck
   language, not just technical jargon.** Found during the 4a checkpoint,
   two layered bugs, fixed in sequence:

   - **Brand-name tautology.** `score_news_velocity`'s original design
     (inherited unchanged from `reference/fetch_market.py`) counted a
     bare company-name mention (e.g. "Vertiv") as a full keyword match.
     Since a ticker's own name appears in nearly every headline about it
     regardless of real news content, and ownership is already
     established via the headline's `ticker` field (not by matching the
     name in text), this made every sub-layer saturate to the 20-point
     cap almost immediately — confirmed on the UNMODIFIED parent
     reference code too (`reference/fetch_market.py --news`, run live,
     showed all 7 of the parent's real layers also at 10.0 the same day),
     so this is a pre-existing bug in the inherited mechanism, not
     something introduced by the sub-layer split. Fix: `config.py` now
     splits each sub-layer's keywords into `brand_keywords` (company
     names) and `context_keywords` (topical/constraint terms).
     `score_news_velocity` requires a `context_keywords` hit for a
     ticker-sourced headline to count at all; brand-name-only no longer
     scores. Generic (non-ticker) headlines still match on either list,
     since brand name is the only way to tie an unattributed headline to
     a company. Ownership filtering itself — which sub-layer/ticker a
     headline counts toward — is untouched and still reused exactly.
   - **Jargon-only context vocabulary.** After the brand-name fix, real
     differentiation appeared, but CIEN (optical) still scored 0/10 despite
     10/10 of its headlines carrying obvious bottleneck content: "backlog
     just hit $8.5B and keeps climbing," "supply constraints," "supply
     risks," "AI optical demand." None matched because the first-pass
     `context_keywords` list was technical-jargon-heavy (`DWDM`, `1.6T`,
     `silicon photonics`) — real financial journalism describes a
     bottleneck in plain language, not spec-level terminology. Fix: added
     `GENERIC_BOTTLENECK_KEYWORDS` (backlog, supply constraint(s), supply
     risk(s), demand outpacing supply, capacity constrained, demand
     surge, sold out, supply tight) to **all 5 sub-layers uniformly**, not
     just optical — a vocabulary gap this general shouldn't be patched as
     a targeted fix on the one layer that happened to disagree with a
     prediction.

   **This is an explicit deviation from Part D1's "reuse the layer-filtered
   news algorithm EXACTLY" rule, scoped narrowly:** the layer/sub-layer-ownership
   filtering mechanism is unchanged and still reused as-is. Only the
   match-counting rule and the keyword vocabulary are not reused
   unchanged — justified by the falsified 4a prediction (all 5 sub-layers
   scoring an identical, non-differentiated 10.0) and confirmed by
   reproducing the same failure in the untouched parent code.

   **Known accepted result, not a remaining bug:** Cooling (VRT) still
   scores 0.0 after the vocabulary fix. All 10 of VRT's current headlines
   are pure stock-price/analyst-sentiment content with no cooling-specific
   or general bottleneck language. Per-ticker/per-sub-layer vocabulary was
   deliberately NOT added to move this number — a real "no constraint
   signal today" read is the intended behavior, not something to
   engineer away.

   **Parent implication, flagged not fixed:** the brand-name tautology
   bug appears to live unmodified in the parent's actual
   `reference/fetch_market.py`/live dashboard too (confirmed saturating
   live). The live parent dashboard itself (miikawir-ops.github.io/AI_valuechain/)
   was found stale — last updated 2026-04-28, ~4.5 months before this
   check — and every one of its 6 layers shows `news_vel: 0` uniformly,
   a separate anomaly (opposite failure mode, not diagnosed further here).
   Whether/how to fix any of this on the parent is a separate decision,
   out of scope for this project — not touched.

## Build order

1. **Data spike** (throwaway, not committed) — pull `quarterly_cashflow`
   capex for MSFT/GOOGL/AMZN/META via yfinance, check clean-quarter depth
   for YoY/QoQ trend calculation. Confirm Yahoo ticker RSS feeds
   (`feeds.finance.yahoo.com/rss/...`) that `fetch_market.py` depends on
   still resolve. De-risks the flagship signal before designing around it.

2. **Repo scaffold + config module** — `requirements.txt`, and a config
   module defining the sub-layer structure (Part B2: cooling/networking/
   optical/compute/colocation → tickers) and the capex-source tickers
   (Part B5). Everything else imports from here.

3. **`score_engine.py`** — copied from `reference/` essentially unchanged:
   three-signal weights, fundamental override, macro multiplier, A/B/C/D
   ratings. No capex-driven changes (decision #1).

4a. **`fetch_market.py` — sub-layer swap only.** Swap the parent's
   `AI_CHAIN_LAYERS` for the 5 sub-layers + Part B5 ticker universe. Reuse
   the layer-filtered news algorithm exactly (non-negotiable per Part A6).
   No capex fetch yet — commit and checkpoint here before adding it.

   **Checkpoint (falsifiable, not just "it runs"):**
   - Before running: write down the expected read per sub-layer (e.g.
     optical hot, colocation cooler, cooling warm) based on the 1.6T
     capex narrative already believed to be true.
   - Per-ticker news scores land in the 0–6 range, not universally capped
     at one end.
   - No ticker's headlines score for a sub-layer it doesn't belong to
     (cross-contamination check — this is the bug class Part A6 exists
     to prevent).
   - Actual output matches the written-down expectation (optical/cooling
     read elevated). If it disagrees, either the belief or the code is
     wrong — both are worth knowing before capex is layered on top.

4b. **`fetch_market.py` — capex-trend fetch.** Add the capex-trend fetch
   for the 4 hyperscalers, kept distinct from the existing per-ticker
   `capex_div` field (naming collision risk — different concepts). Only
   start this once 4a's checkpoint passes, so a later problem in optical
   scoring can't be confused with a capex bug.

5a. **`main.py` — aggregation only.** Adapt aggregation from 7 layers to
   5 sub-layers. Reuse market-cap weighting, bottleneck leader boost,
   3-day confirmation as-is. Apply decisions #2 and #3 for single-ticker
   sub-layers. No capex logic yet — commit and checkpoint here.

5b. **`main.py` — capex direction + beneficiary map.** Add the capex
   direction classification per decision #4 (single-quarter YoY snapshot,
   named thresholds, no nearest-quarter fallback, insufficient-data
   surfaced not dropped) and the static beneficiary map (Part B3),
   consumed by render, not by score_engine. Document the Part B4 boundary
   directly in the
   `CAPEX_BENEFICIARY_MAP` config: this map covers in-building power
   distribution only (PDUs, UPS); site-level power delivery (generation,
   grid, transmission, substations) belongs to the parent's Energy layer
   and is out of scope here. Written at the exact place a future
   power-related signal would be added, so the boundary isn't just prose
   in the spec — it's on the code path where someone would otherwise miss
   it.

6. **`render.py`** — adapt layer cards to the 5 sub-layers. Add the
   top-level capex-direction strip and per-sub-layer beneficiary badge as
   a display-only addition (decision #1). Keep the dark hero/visual system
   as-is for family consistency (Part A5).

7. **Deploy plumbing** — `index.html` at repo root (required for GitHub
   Pages bare-URL resolution, per CLAUDE.md), GitHub Actions workflow,
   `publish.py` adapted from `reference/`. Remote not created yet — local
   repo only until there's something to deploy.

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
   different number for AMZN). **"4-back" means 4 positions back on the
   raw column index (gaps included) — not position 4 after `dropna()`.**
   `dropna()` compacts the column list, so if any column in between is
   NaN, its post-dropna position 4 silently points at the wrong fiscal
   quarter with no error or visible sign it happened — quietly breaking
   the seasonality control this method exists for.

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
     B2), resolved after seeing 4b's real fetched numbers — not inline
     judgment calls in 5b, and not guessed blind.**
     `CAPEX_YOY_ACCELERATING_PCT = 0.30`, `CAPEX_YOY_DECELERATING_PCT =
     0.05` (>30% YoY = accelerating, <5% = decelerating, 5–30% = stable).

     **Reasoning (verified history — corrects an earlier unverified
     guess):** pre-AI hyperscaler capex growth ran up to ~30–43% in
     strong years (2018: +43%; 2016–2020 average: ~32%) and near-flat in
     soft years (2019: +1% aggregate) — not "high-single-digit to 20%"
     as first assumed. The current AI-driven regime has run at roughly
     70–80%+ YoY sustained since approximately Q2 2023. The 4b real
     readings (2026-09-17: MSFT +109.6%, GOOGL +100.1%, AMZN +76.7%,
     META +82.1%) are consistent with an already-established multi-year
     regime, not a fresh spike.

     **Expected consequence, not a defect:** with these thresholds,
     "accelerating" should be expected to read true for an extended
     period while the current supercycle holds — an accurate reflection
     of a real, sustained regime, not a sign the thresholds are stuck or
     miscalibrated. This is distinct in kind from the 4a news-scoring
     saturation bug (decision #5): that was one shared artifact pinning
     every sub-layer to an identical 10.0 regardless of real content;
     this is four genuinely differentiated real values (76.7–109.6%, a
     33-point spread) that happen to all clear one threshold because the
     underlying trend genuinely is that strong across all four
     hyperscalers right now.

     **GOOGL fragility (observed on the 4b real run):** GOOGL returned
     exactly 5 quarters total from `quarterly_cashflow`, and the 4-back
     slot landed precisely on the 5th (oldest) column, which happened to
     be non-null — it passed this run with zero margin, not comfortably
     clear of the edge. If yfinance ever trims GOOGL to 4 quarters, or
     that oldest column goes NaN, GOOGL flips to insufficient-data
     immediately. Not a bug — the exact fragile case the no-fallback
     rule above exists to handle correctly rather than mask.

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

6. **Missing-data convention (fetch stage): `None` + `data_missing` list,
   not silent 0/empty.** Applied across `fetch_market.py`'s per-ticker
   fetch (`fetch_ticker_data`) and macro fetch (`fetch_macro`) — every
   field that previously defaulted to 0/empty on a failed or absent fetch
   now returns `None` and appends its field name to that ticker's (or
   macro dict's) `data_missing` list. Two deliberate exceptions, both real
   zeros rather than failures: `analyst_upgrades` stays `0` when the API
   call succeeds but returns no matching recommendations (only an actual
   call failure sets it to `None` + missing); `peer_outperformance`
   derives from `price_30d_return` and is left `None` without its own
   `data_missing` entry when the root field is already flagged, so one
   failure isn't double-counted as two.

   News-fetch failures: if a ticker's own RSS feed fetch fails,
   `news_velocity` is `None` + missing — even if generic headlines still
   came through — because the ticker-specific feed is the heavier-
   weighted (2×) primary signal and a 0.0 computed without it isn't
   trustworthy. Generic-feed failures aren't attributable to one ticker;
   they're surfaced as a top-level `meta.generic_feed_failures` list on
   `run_pipeline()`'s return value (and a top-level `⚠` flag in the CLI
   output), not injected into every ticker's `data_missing`.

   **`score_engine.py` (step 3) and `render.py` (step 6) don't exist yet**
   — this fix covers the fetch stage only. When those files are built,
   they inherit the contract: no scoring calculation may let a `None`
   flow through arithmetic as if it were 0 — exclude the input and note
   the exclusion, or mark the whole score "insufficient data" when the
   field is load-bearing (e.g. `news_velocity`) — and the render layer
   must display any field/score derived from missing data as visibly
   distinguishable from a real 0.0 or real score.

   **`score_engine.py` implemented (2026-09-17) — three tiers, not a
   binary full/insufficient split.** `reference/score_engine.py`'s own
   `_get(default=X)` helper turned out to be the same anti-pattern one
   level up — it silently substituted a neutral default for any missing
   field and kept computing (per spec D3's "reuse the design, not a bug
   found empirically" rule, this is exactly the case that rule exists
   for). Replaced with: **field-level** — a missing input excludes that
   sub-component and renormalizes the stage's remaining weights;
   **stage-level** — a stage with zero usable input is dropped and the
   top-level 65/20/15 weights renormalize across the remaining stages;
   **ticker-level** — score is `None` ("insufficient data") only when
   acceleration (65% weight, the primary bottleneck detector) has zero
   usable input at all (`growth_curr`, `growth_prev`, AND `gm_delta` all
   missing). `news_velocity` alone does NOT trigger this, despite being
   the example named above — at its actual composite weight (20% x 60%
   = 12%), nuking the whole score over it would over-flag routine gaps.

   Every result also carries `stages_used` (which of the 3 top-level
   stages had usable input) and `reduced_input` (`True` if ANY field was
   excluded anywhere, even one sub-component) — a coverage/confidence
   marker per Part A4's data-honesty principle. Threshold set low
   (any exclusion, not just a stage collapsing to one surviving input)
   deliberately: the point is making a reduced-input score visibly
   distinguishable from a fully-supported one, not just flagging severe
   cases; render decides how prominently to surface it.

   Two more reference bugs of the same class found and fixed while
   building this, neither previously documented: (1) the error-path
   fallback on an unhandled exception returned `score: 0.0, color:
   "Green"` — a crash silently became indistinguishable from a real
   neutral reading; now `score: None`. (2) `get_macro_multiplier()`'s
   `self.macro_data.get("vix", 20.0)` pattern only applies its default
   when the key is ABSENT — `fetch_macro()` now returns the key present
   with value `None` on failure (this same decision), so the old pattern
   would have returned `None` itself and crashed on `None > 30`. Fixed
   to skip a missing macro signal from the vote entirely; if all 3 are
   missing, returns an explicit `"Unknown (macro data unavailable)"`
   regime at 1.0x rather than computing Risk-Off/Neutral from nothing.

   **Verified against live VRT data before the main.py commit:** fetched
   VRT fresh (2026-09-17) through the real pipeline path (including
   `add_peer_outperformance`) and ran it through the new engine.
   `revenue_quarterly` was the only fetch-stage gap, and it isn't
   consumed by any `calculate_*` stage — result was `data_missing: []`,
   `reduced_input: false`, `data_status: "Full"`. The acceleration-
   insufficient path did NOT trigger. This is not a routine outcome for
   VRT as of this data — B8's "shows which sub-layer is bottlenecked"
   criterion isn't threatened by data completeness for Cooling right
   now. Not a permanent guarantee — re-check if a future run shows
   otherwise.

7. **Cadence: start daily-only, add weekly deep once stable.**
   Chronologically this belongs with decisions #1–3 — it was made at the
   project's original scoping, before PLAN.md existed in its current
   numbered-decisions format, alongside the capex-overlay-only and
   single-ticker-weighting calls. It simply never got a formal numbered
   entry until now; recorded retroactively rather than left to read as
   an unresolved open question in the spec. Numbered #7 (after the later
   mid-build decisions #4–6) only to avoid renumbering entries already
   cross-referenced elsewhere in this file, `fetch_market.py`,
   `config.py`, and `DATACENTER_RAYDAR_SPEC.md` — the number doesn't
   reflect when the decision was actually made. Matches
   `DATACENTER_RAYDAR_SPEC.md` Part B6's original recommendation
   ("Recommend starting daily-only, add weekly deep once stable").
   Revisit at build-order step 7 (deploy plumbing), when a real run
   cadence is actually needed.

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

   **Not yet built.** Contrary to this build order, step 4a ran before
   this step — the 4a news-scoring checkpoint (sub-layer swap + cross-
   contamination check) only needed `fetch_market.py` and `config.py`,
   not `score_engine.py`, so building it wasn't a blocker and was
   deferred. This is an accepted reordering, not an oversight to backfill
   silently — build it when this step is actually reached, applying
   decision #6's missing-data contract from the start.

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

   **Two persistence files, both intentional, neither previously
   documented:**
   - `audit_log.json` — written by `score_engine.py`'s `_append_audit()`
     once per ticker on every run (rolling log, capped at 500 entries:
     score/color/regime/sub_scores/fund_delta/stages_used/data_status).
     Generated and working now. Nothing reads it yet — write-only audit
     trail, carried over from the reference design.
   - `scores_history.json` — `main.py`'s 3-day color confirmation
     (`_load_recent_layer_scores`/`_confirmed_color`) **reads** it; the
     **write** side is `render.py`'s `save_scores_history()` in the
     reference (step 6, not built yet). Doesn't exist on disk yet — every
     run currently falls into "unconfirmed — building baseline" until
     step 6 exists. Both are in `.gitignore` (runtime artifacts, not
     source) — `scores_history.json` was added there pre-emptively when
     5a was built, anticipating step 6, not because anything writes it
     today.

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
   as-is for family consistency (Part A5). Apply decision #6's missing-
   data contract: any field/score derived from a `None`/`data_missing`
   value must render as visibly distinguishable from a real 0.0 or real
   score, not silently plausible.

7. **Deploy plumbing** — `index.html` at repo root (required for GitHub
   Pages bare-URL resolution, per CLAUDE.md), GitHub Actions workflow,
   `publish.py` adapted from `reference/`. Remote not created yet — local
   repo only until there's something to deploy.

## Known issues (recorded, not fixed)

- **`python fetch_market.py --news` crashes on Windows with
  `UnicodeEncodeError`.** The CLI output uses `█` (news-velocity bars) and
  `×` (weight labels); Windows terminals default to the `cp1252` codepage,
  which can't encode either character, so the crash is reproducible on
  any Windows shell that hasn't been forced to UTF-8
  (`PYTHONIOENCODING=utf-8` works around it). Found during the missing-
  data-convention verification (2026-09-17), unrelated to that fix —
  pre-existing in the original `--news` print statements. Not fixed;
  noted here so it isn't lost before someone hits it unprepared.

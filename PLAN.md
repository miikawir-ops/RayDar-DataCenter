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

## Open questions (flagged, not resolved)

Unlike "Decisions settled" above, nothing here has been decided. Recorded so
findings don't get lost, not because a fix or a direction has been agreed.

1. **Red (the flagship "confirmed bottleneck" threshold) structurally
   cannot fire on constraint signal alone — in tension with B3's "surface
   before revenue confirms" framing.** Found 2026-09-18 while checking
   why optical read all-Green despite CIEN's real, correctly-detected
   backlog/supply-constraint news (the 4a keyword fix's own finding).

   The constraint calculation itself is not diluted or broken — CIEN's
   `constraints=67.04` traces cleanly from real `news_velocity=7.0` and
   `capex_div=0.407`, including the both-signal bonus firing correctly.
   The ceiling is architectural: composite = accel×0.65 + constraints×0.20
   + smart×0.15.

   - **Orange (45) is reachable from constraint signal alone** at
     optical's actual acceleration levels today (~35–48). COHR
     (`capex_div=1.0`, constraints=94.3, accel=48.33) already clears it
     this way. Generalizing: maxing constraints alone would push CIEN's
     41.05 to ~47.6 — also across the line.
   - **Red (65) requires `accel×0.65 + smart×0.15 ≥ 45`, independent of
     how strong constraints gets** (constraints maxes out at 20 of the
     100 points). At optical's realistic smart_money levels (5–12), that
     means accel needs to reach roughly 67–69 — real acceleration-stage
     strength (growth delta, growth level, or margin — not necessarily
     narrow QoQ "acceleration"), not just a strong constraint reading.
     None of the 4 optical tickers are within 20+ points of that today.

   This weighting is inherited, unmodified parent logic (D1: "reuse the
   three-signal structure... AS-IS," weights untouched per Part B). The
   tension: B1/B3 describe constraint/capex signals as the *leading*
   indicator, surfacing before revenue confirms — but the model's most
   decisive threshold (Red) structurally requires revenue-side strength
   to already be present, which sits close to the opposite of "leading."

   **Explicitly unresolved.** Not a bug — the constraint calculation and
   the aggregation both work correctly as designed. Not yet decided
   whether this is the correct calibration for this project's stated
   purpose, or a real gap worth reweighting later. No direction agreed;
   do not treat silence on this as approval to change the weights, and
   do not treat it as closed/accepted either.

   **Launch decision (2026-09-20): going live with this open, not
   blocking.** This question can only be evaluated against weeks of real
   running data — whether Red genuinely never fires when it should, or
   whether the weighting is fine and today's data simply hasn't produced
   a case that needed it — not against a single snapshot from one or two
   days of runs. Holding launch until it's resolved would mean waiting
   on data that launching is what generates. **Still not resolved** —
   this is a decision to launch with it open and tracked, not a decision
   about the question itself. Revisit once there's real multi-week
   history to actually judge against.

   **No multi-day history has been collected since launch (found
   2026-10-09, ledger R28).** The "revisit once there's real multi-week
   history" condition above can't be met as things stand: CI never kept
   `scores_history.json`, so the dashboard holds one day at a time. The
   Actions run logs do record each run's per-sub-layer weighted score
   and colour (plus the best ticker and its score) for 15 days,
   2026-09-20 to 2026-10-09 (the 2026-10-05 run failed), which is enough
   for a rough look at sub-layer trends. They don't record the
   per-ticker acceleration/constraints/smart-money breakdown this
   question turns on. Logs are kept 90 days, so the earliest expire
   around 2026-12-19.

2. **Family cross-linking — one convention settled, the broader plan is
   still open.** B7's parent↔Data Center link is now built in both
   directions (`AI_valuechain`'s `infra` layer card → here; here's hero
   + footer → `AI_valuechain`). The wider question — a shared,
   data-driven nav across every RayDar-family site (RayDar Vice, TP
   Special Agent, Café Ellu, Quantum RayDar once built), which pattern
   to standardize on, and whether tax-domain agents belong in the same
   navigation as the investment dashboards — is unresolved, tracked
   separately, not decided here.

   **Settled (2026-09-21): same-tab vs new-tab convention for family
   links.** "Up/back" navigation to the parent uses the same tab — this
   hero link is the first family link anywhere that doesn't open
   `target="_blank"`, a deliberate exception, not an oversight. Reasoning:
   it's a navigational move within one coherent family experience (going
   back up), not a reference opened alongside the current page — and it
   avoids tab pile-up on the common parent → Data Center → back path.
   Every other family link (footer, sibling references, `AI_valuechain`'s
   own Data Center card link) stays `target="_blank"`. The future family
   cross-linking plan should formalize this same-tab/new-tab convention
   explicitly rather than leave it to be inferred from this one instance.

   **Live and verified (2026-09-21).** Ray confirmed both links in a
   browser on the deployed site: hero "← RayDar AI value chain" opens
   in the same tab as intended, footer "Part of the RayDar family" opens
   in a new tab as intended. The parent↔Data Center cross-link is now
   genuinely two-way, not just built — click behavior confirmed, not
   just markup-inspected.

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

     **Update (step 6, 2026-09-18): the write path is verified** —
     `render.py`'s `save_scores_history()` ran against live data and
     produced a real `scores_history.json` entry. **The read-back side
     (3-day color confirmation logic) is still unverified against real
     multi-day data** — only one day of history exists as of this run,
     so `_confirmed_color()`'s actual confirm/hold/instant-Red branches
     have never fired on real data, only been exercised in isolation
     during earlier design work. Needs a real check after 2-3 more daily
     runs accumulate enough history — not now. Flagged so this doesn't
     get silently assumed solid just because the file exists and the
     write succeeded.

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

   **`CAPEX_MIN_REPORTING = 2` rationale, stated honestly:** rules out the
   degenerate case (0-1 of 4 reporting would just be one company's number
   mislabeled as a market-wide aggregate) — that part is a real
   justification. It does NOT establish why 2 specifically rather than 3
   (a stricter majority-of-4 bar); 3 would be a legitimate, arguably more
   conservative choice given GOOGL's documented fragility (decision #4).
   That tradeoff wasn't actually weighed when 2 was picked — this isn't a
   data-derived cutoff like the YoY thresholds, it's the simplest floor
   above the degenerate case. Revisit if a real run ever drops below 4/4
   and the 2-vs-3 choice starts to matter in practice.

6. **`render.py`** — adapt layer cards to the 5 sub-layers. Add the
   top-level capex-direction strip and per-sub-layer beneficiary badge as
   a display-only addition (decision #1). Keep the dark hero/visual system
   as-is for family consistency (Part A5). Apply decision #6's missing-
   data contract: any field/score derived from a `None`/`data_missing`
   value must render as visibly distinguishable from a real 0.0 or real
   score, not silently plausible.

7. **Deploy plumbing.** In progress (2026-09-18).

   **Correction: no `reference/publish.py` exists to adapt from.**
   `reference/` contains exactly 4 files (`fetch_market.py`, `main.py`,
   `render.py`, `score_engine.py`) — confirmed by listing the directory.
   No `publish.py`, no GitHub Actions workflow, no `.github/` anywhere in
   this repo or in `reference/`. This step's original wording ("`publish.py`
   adapted from `reference/`") was a wrong assumption; corrected here
   rather than left standing. Built from general GitHub Pages deploy
   knowledge instead — no separate `publish.py` file at all, the workflow
   YAML handles fetch/score/render/deploy declaratively.

   **Deploy model: Actions-based artifact upload, not commit-back.**
   `.github/workflows/deploy.yml` runs `python main.py --now` (writes
   `index.html` locally exactly as any local run does — unaffected by
   this choice), copies just that file into a `_site/` staging dir (not
   the whole repo), and uploads it via `actions/upload-pages-artifact` +
   `actions/deploy-pages`. `index.html` is never committed to git —
   avoids noisy diffs from dynamic content (prices/scores/timestamp
   changing every run) and matches GitHub's current recommended approach
   over the older branch-based model.

   **No secrets required.** Confirmed by grepping this project's fetch
   code and `reference/fetch_market.py` for API-key/env-var usage — none
   found. `yfinance` and the RSS feeds `fetch_market.py` depends on are
   both unauthenticated. The workflow's `pages: write` / `id-token: write`
   permissions are declared in the YAML itself, not manually-created
   secrets; `GITHUB_TOKEN` is provided automatically by Actions.

   **Schedule: weekdays only (`0 12 * * 1-5`, 12:00 UTC), deliberately —
   not an unexamined default.** Markets are closed weekends: no new
   prices, sharply reduced news/filing volume. A weekend run would just
   re-fetch Friday's numbers with a new timestamp — not harmful, but a
   wasted run with no new signal. Matches real precedent:
   `reference/main.py`'s own `scheduled_job()` explicitly skips weekends
   (`is_weekday()` check) for the same reason. Decision #7's "daily" is
   read as "daily while markets are open," not literally every calendar
   day.

   **`requirements.txt` created** (`yfinance`, `feedparser`) — named in
   step 2 but never actually created; inferred from the real imports
   across every `.py` file in this project (not `reference/`, which
   pulls in `schedule`/`dotenv` for features already dropped here).

   **Not live yet, deliberately.** Repo pushed to
   `github.com/miikawir-ops/RayDar-DataCenter` (2026-09-19, `main`
   branch) — but Pages is still not enabled (Settings → Pages → Source:
   GitHub Actions), gated on the still-open private/public repo + GitHub
   plan question. Remote creation and repo visibility remain separate,
   explicitly-gated decisions.

   **First manual `workflow_dispatch` run (2026-09-20) — fully verified,
   all four checks:**
   - **CI dependency resolution: verified.** `pip install -r
     requirements.txt` resolved cleanly in CI — no version conflicts, no
     source builds, all cp312 wheels. Confirms `requirements.txt`
     (created by inference from this project's actual imports, not
     ported from anywhere) is sufficient in a clean environment.
   - **Failure point: verified as expected.** Only `deploy-pages` failed,
     with the expected 404 and GitHub's own message naming Pages-not-
     enabled as the cause. The Pages artifact built and uploaded
     successfully before that (`artifact_id: 10600248442`) — only the
     Pages handoff failed, nothing upstream.
   - **CI data-fetch behavior: verified.** The `python main.py --now`
     step log (run 2026-09-20, 06:48 UTC) shows real data fetched from
     GitHub's runners: 120 ticker-specific + 50 generic headlines, all
     12 tickers fetched successfully across all 5 sub-layers (1/1
     cooling, 2/2 networking, 4/4 optical, 3/3 compute, 2/2 colocation),
     live macro (VIX 14.81, yield +30.2bps), sub-layer weighted scores
     29.9–44.3 (all Green), and capex 4/4 hyperscalers reporting at
     92.1% avg YoY — consistent with local run ranges. No HTTP 429s, no
     empty results, no CI-only `data_missing` entries, and per-ticker
     fetch timings (~0.5–1s sequential) consistent with genuine network
     calls.

     **Conclusion, now evidence-based rather than inferred:**
     unauthenticated `yfinance`/RSS access works from GitHub Actions
     runners. No authenticated data source is required, and no API key
     or GitHub Secret is needed — this supersedes the earlier
     code-grep-based inference with a verified real-environment result.
   - `scores_history.json` confirmed writing in CI (`Scores history
     saved (1 days)`). **Corrected 2026-10-09 (ledger R28):** this
     bullet used to say multi-day color-confirmation data "will
     accumulate once scheduled runs begin". It doesn't. Every run starts
     from a fresh checkout where the file doesn't exist (it's gitignored,
     and deploy.yml has no cache, artifact download or commit-back), so
     each run logs `Scores history saved (1 days)` and confirmation never
     leaves "building baseline". The read-back verification item noted
     earlier in this section was never satisfied.
   - **Lesson (2026-10-10, ledger R34): before replacing a parent
     mechanism, list everything it did.** The parent's commit-back step did
     two jobs: it published `index.html` and it persisted the score history
     (by committing both). The Actions-based Pages deploy replaced the first
     and silently dropped the second, and nothing noticed for three weeks
     because every run still "worked". When swapping out a mechanism
     inherited from the parent, enumerate its side effects first (files it
     writes, state it carries between runs, what reads that state) and
     check each one has a new home.

   **LIVE (2026-09-20).** Repo made public, Pages enabled (Settings →
   Pages → Source: GitHub Actions), deploy verified working end to end.
   Dashboard is reachable at `miikawir-ops.github.io/RayDar-DataCenter/`.
   Weekday cron (`0 12 * * 1-5`) is now active — the first scheduled
   (non-manual) run will fire on the next weekday.

   **Correction (2026-10-06): the Pages source was in branch mode, not
   "GitHub Actions" as recorded above. Fixed the same day.** The Pages API
   reported `build_type: legacy` ("Deploy from a branch", `main`, `/`), with
   branch builds running on every push since at least 2026-09-22 (the
   earliest in the API's history). Branch mode was not fully replacing the
   Actions deploys: both deployed to the same site, and whichever finished
   last was live.
   - A branch build serves the raw repo, and the dashboard `index.html` is
     generated in CI and gitignored. So **every push 404'd the dashboard
     root** (`/` and `/index.html`) until the next Actions run, while
     committed files (`ecosystem.html`, `business-models/`) kept working.
   - Confirmed on 2026-10-06. Ray's push at 11:44 UTC took the root down.
     The step 8 push at 12:39 did the same: its branch build landed after
     the manual Actions deploy. A second manual run brought the root back
     at 12:44.
   - Proof of the mechanism: the deployed artifact itself contained
     `index.html` (82,902 bytes), and cache-busted requests still returned
     404 from the origin.
   - **Fixed at 12:47 UTC:** Pages switched to `build_type: workflow` via
     the API (Ray's call), then the workflow was re-run green. Dashboard
     root, `ecosystem.html` and `business-models/` all load live, with no
     JS errors.
   - How it got into branch mode isn't known. Not investigated further.
   - Also seen: the 2026-10-05 scheduled run shows "failure", but its job
     was cancelled by GitHub after 15 minutes without running any step and
     has no logs. It looks like a runner issue, not a code issue. The next
     day's runs were green.

   **Two things checked on the live site before calling this done:**
   - **Heat trail at n=1 day of history: confirmed correct, not a bug —
     but visually ambiguous, worth revisiting.** Pulled the live page's
     embedded `HISTORY` data directly: exactly 1 real day (2026-09-20,
     all 5 sub-layers Green), 89/90 days still `"none"`. `buildHeat()`'s
     default 7-day view filters its display slice to only real-data
     days, and the grid's `minmax(32px,1fr)` column sizing stretches a
     single real day to fill the full row width — which is what reads
     as "solid full-width green bars." Not fabricated data, correctly
     showing the one real day that exists. ~~Confirmed by code review
     (not yet observed live) that it will correctly grow into a genuine
     multi-day trail as `scores_history.json` accumulates.~~ **Corrected
     2026-10-09 (ledger R28):** the code review covered only the
     rendering. The history it reads never accumulates in CI (see the
     correction above), so the trail has shown exactly one real day on
     every run since launch; live check 2026-10-09: 1 of 90 days real.
     **The
     ambiguity:** 7 real green days (7 narrow columns) could look
     visually similar to today's 1-day-stretched state at a glance,
     without hovering per-cell tooltips. Revisit once real multi-day
     history exists to see whether it actually reads clearly, or needs
     a visual treatment for low-history states (e.g. an explicit
     "building history" label instead of stretching one day wide).
   - **"Deep dive with Claude" button — documented, not just inherited.**
     In the ticker expand panel, opens `claude.ai/new?q=<prompt>` in a
     new tab, pre-filling a claude.ai conversation about that ticker or
     sub-layer. No API call from the page, no credentials, nothing sent
     except the prompt text (ticker/company info already visible on the
     page) in the URL — visitor needs their own claude.ai account to see
     a response. The mechanism (`sendPrompt()`, the `window.open(...)`
     pattern) was ported unchanged from `reference/render.py`; the
     prompt text itself was rewritten during this build for data-center
     context. This was a deliberate keep-decision made during the
     render.py build but not previously called out as its own
     documented item — done now since it's a user-facing interactive
     element on a now-public page.

8. **Finnish business-models explainer (`business-models/`).** **COMPLETE
   (2026-10-07): all 11 pages live and linked from the ecosystem page.**
   Started 2026-10-06. Eleven Finnish pages on data center business models,
   ported from Ray's approved Claude Design export ("Tilanne 9/2026"; the
   export is kept outside git in `Output/business-models-source/`): the hub
   (one pager), five model cards, value chain, financing, specialised
   models, Why Finland, glossary. A fourth level beside the dashboard and
   the ecosystem page, in the light editorial style of spec A5b, not the
   dark dashboard look.

   **Step 1: scaffold + hub. LIVE since 2026-10-06** at
   `miikawir-ops.github.io/RayDar-DataCenter/business-models/` (unlisted).
   Ray approved it, and from step 2 on approved working in batches: each
   batch is implemented, verified and committed, with screenshots shown
   once per batch. Verified live after a green manual run: HTTP 200, all
   chrome and 13 glossary terms working, fonts served from the site, no
   third-party requests, no JS errors. Commits:
   `cfd46f3` (.gitignore no longer drops `business-models/index.html`),
   `3a3eaba` (spec A5b, CLAUDE.md live status), `12bbf05` (scaffold + hub),
   `fe1e857` (deploy.yml copies the folder), `63d20af` (header "Tilanne"
   removed), `c53030b` (this record), `109f35d` (English slugs and glossary
   keys).

   **Decisions settled (2026-10-06):**
   - Header and footer are rendered by `assets/chrome.js` from one page list.
   - Fonts are self-hosted, with no third-party requests.
   - Slugs serve as both deep-link hashes and file names, in English
     (`#gpu-cloud`, `gpu-cloud.html`). Changed from Finnish slugs on
     2026-10-06, before the first push, together with English glossary
     keys. All visible text stays Finnish.
   - The "Tilanne 9/2026" marker sits in each page's own kicker and in the
     footer, not in the header. The glossary page's kicker has none, so the
     footer is its only marker.
   - **Model cards (step 2): drop the in-page 1→5 stepper.** The shared
     header stepper replaces it.
   - **No entry link to the hub until all ten subpages are ported.** It stays
     reachable by URL only, so visitors don't land on a hub whose links lead
     nowhere. Until then, no live page may link to an unported page.
     Revisit when the set is complete.
   - Glossary:
     - The 68 terms live in `assets/glossary-fi.js`, the single source of
       truth. `sanasto.html` will render from it.
     - One floating, viewport-clamped tooltip (`assets/glossary.js`), using
       the same markup and data shape as `ecosystem.html`.
     - Tagging rule: each term once per page, at its first appearance in
       running text, never in headings or labels.
     - Tooltips use the glossary page's wording. Some per-page term footers
       word the same term differently, and the footers stay as authored.

   **Verification method for every ported page:**
   - `tools/check_port_text.py`: every word of the source is kept, in order.
   - A pixel diff against the source at 1680px. Deviations must be explained
     by deliberate changes, as shown by re-imposing the source's constraints
     in a test run.
   - Playwright functional checks from 1680px down to 360px.

   **Every explainer change runs all three checks (Ray, 2026-10-08)**, from the
   repo root with the site served locally
   (`python -m http.server 8765 --bind 127.0.0.1`):
   - `python tools/check_port_text.py --all`: text identity with the approved
     source, after the registered deviations.
   - `python tools/check_layout_sweep.py`: layout at every width from 1024 to
     1680px, on all 11 pages.
   - `python tools/check_interactions.py`: chrome, navigation, tooltips, deep
     links and swipe, 1680px down to 360px (565 checks in three suites: hub,
     cards, pages). Add `--shots Output/screenshots/business-models` for the
     review screenshots.

   All three must pass before a commit. The interaction checks used to live in
   a temporary session folder outside the repo, where one went stale unnoticed
   (it still targeted the header's old back link). That's the same failure
   mode as the dropped instructions (see the requested-changes ledger), so they
   moved into `tools/`. The pixel-diff scripts used while porting stay outside
   the repo by Ray's decision (2026-10-08, ledger R13): they're needed only
   when re-porting from a new design export. They sit in a temporary session
   folder that may not survive, so a re-port may have to rebuild them from the
   method above: screenshot the source and the port at 1680px, re-impose the
   source's fixed canvas constraints on the port, and diff.

   For the hub: 641 words identical. Pixel-identical at 1680px apart from
   rows growing to fit their text and no fixed canvas height. 56/56
   functional checks pass. Touch was tested in Chromium emulation only, not
   on a real device.

   **Batch 1: the five model cards. LIVE 2026-10-06** (pushed on Ray's go;
   verified live: all five 200, correct current step, every glossary tag
   working, hub headings linking to them, dashboard root and ecosystem page
   unaffected). `public-cloud`, `gpu-cloud`,
   `retail-colocation`, `wholesale-colocation`, `own-data-center` `.html`.
   - The in-page stepper is dropped (header stepper instead), and the hub's
     model headings now link to their cards.
   - Shared card components are in `explainer.css`. Fill classes are now
     named by colour (`fill-blue`, `fill-green`, …): the role a colour
     stands for differs per card, and each card's legend says which.
   - Text check: every word identical (436–490 words per card) after
     removing only the declared stepper.
   - Pixel diff at 1680px: 0 differing pixels outside the dropped stepper.
     That's with the glossary spans unwrapped for the test only, since a
     span shifts sub-pixel glyph positioning.
   - **Found in the source:** the fixed 1460px canvas squeezed the dark
     "Tilanne / Päätös / Vertailukohta" band on cards 1, 2 and 4. On cards 2
     and 4 this cut off 2–4px of the band's last text line. The port gives
     the band its natural height, so those pages are 10–24px taller.
   - Below 1280px the card body stacks; at 1024px the two authored columns
     would leave the layer column 75px wide.
   - 228/228 functional checks pass at 1680, 1280, 1024, 820, 390 and 360px.
   - Glossary tags follow each card's own term list. Terms that appear only
     in labels stay untagged (Vastapuoliriski, Jäännösarvo, Demarc,
     Developer, Ennakkomaksu).

   **Batch 2: value chain, financing, specialised models, Why Finland,
   glossary (2026-10-06).** Completes the eleven pages.
   - Text check: every word identical (value chain compared as 42 text
     blocks, since its canvas source isn't in reading order).
   - Pixel diff at 1680px: 0 differing pixels on all five.
   - value-chain: the canvas is now normal flow on one shared grid. On
     narrow screens the diagram keeps its full size in a sideways scroller
     (Ray's call; stacking the chains was offered as the alternative).
   - glossary: renders from `glossary-fi.js`, with linkable cards (#g-<key>).
   - **Found in the source:** financing's approved design overflowed its
     1870px canvas by 78px, hiding the bottom of the term panel and the fine
     print, which carries the caveat that the xAI arrangement is
     unconfirmed. The port restores it. **This is the second clipping bug in
     the source design**, after the model cards (cards 2 and 4 cut 2–4px off
     the dark band's last line). Both have the same cause: a fixed-height
     Claude Design canvas whose content is taller than the canvas. Lesson
     for any future re-export: compare each source's content height with its
     canvas height (`scrollHeight` vs the board height) before trusting the
     canvas view as the approved look, because what the canvas hides was
     never seen in review.
   - **Navigation (Ray, 2026-10-06):** the five page titles as links in the
     header's top row ("Sivut" menu below 1280px), plus hub links from the
     value-chain and specialised-models panel titles and "Termit:" to their
     pages. Slugs: value-chain, financing, specialised-models, why-finland,
     glossary.
   - 279/279 checks on the new pages; hub and cards re-verified.
   - **Hub entry link: LIVE 2026-10-07** (`1547581`, approved by Ray from the
     1680/1280 screenshots). It is a banner on the ecosystem page, in the
     dashboard's ecosystem-banner style. **Moved 2026-10-07 (Ray)** from below
     the explanation section, where most readers never reached it, to the top
     of the content: full width, directly below the hero and above the
     Poster/Relationship-explorer toggle. It is the single entry point (the
     bottom copy was removed), with a computed style identical to the live
     dashboard banner. Text: "📊 Datakeskusten liiketoimintamallit — how data center capacity
     is bought, leased and financed (explainer in Finnish) →". Verified live:
     the banner shows, opens `business-models/` in the same tab, and the
     dashboard root and hub still load with no JS errors.

   **Status: the explainer is complete** (11 pages live, linked from the
   ecosystem page). Only the separate rounds below remain.

   **Hub laptop-width fix (2026-10-07).** Ray hit three bugs on his laptop.
   His display settings vary, so the fix targets the whole 1024–1680px range
   rather than one configuration. Reproduced by width sweep first:
   - "Kuka kantaa riskin" boxes overflowed their card below ~1366px (23px at
     1280). They now stack when the column is too narrow, in all five columns
     together.
   - The legend's third key wrapped alone below ~1440px. The keys now wrap as
     a group.
   - Heading wraps (Wholesale-colocation below ~1400px, VAIHE 1's label below
     ~1270px) left the other columns' labels misaligned. The stage label and
     model name are now separate subgrid rows.
   - 1680px parity is unchanged.
   - **Why the earlier 1280px check missed it:** the overflow check only
     tested vertical overflow, at a few fixed widths. `tools/check_layout_sweep.py`
     now sweeps every width and checks horizontal escape too. Run it after any
     explainer layout change.
   - **Fixed (Ray, 2026-10-07):** below ~1380px the hub's mini value chain
     scrolled sideways inside its panel, with 63px hidden at 1263 and its last
     box behind the edge fade, undercutting the diagram's "models form chains"
     point. Below 1400px the bottom row's three panels now stack, so the chain
     gets the full width. Verified: no sideways scroll at any width from 1024
     to 1680px, the sweep is clean on all 11 pages, and 1680 is unchanged
     (still side by side).

   **Cross-links and content changes (2026-10-08, Ray):**
   - **Family links:** the three sites now reach each other in one step, with
     the same cards and icons (📈 Daily signals, 🗺️ Ecosystem map,
     📊 Liiketoimintamallit):
     - dashboard: a two-card row in place of the single ecosystem banner;
     - ecosystem page: a two-card row at the top, in place of the explainer
       banner and the hero's "← Back to dashboard";
     - explainer: header pills plus the footer.
     Cross-links call the dashboard "Daily signals" (it's the live,
     updating site; the other two are static reference). The dashboard page
     itself keeps its title. Commits 66d93b8, e9e056d, b686d52.
   - **Review-date label** reworded from "TILANNE 9/2026" to "TIEDOT TARKISTETTU
     9/2026" (kickers on 10 pages plus the footer on all 11), so it plainly
     means the facts were verified then. **The date is bumped only when the
     facts are actually re-verified, never as routine monthly upkeep.** The
     source's fine-print "Tilanne syyskuu 2026" sentences (financing,
     specialised models, Why Finland) are body text, not the label, and were
     left as authored.
     **Updating a single fact (Ray, 2026-10-08, ledger R16):** a page's label
     rises only after a full pass of all that page's facts. A fact updated on
     its own gets its source and "tarkistettu MM/YYYY" in the page's fine
     print, and its URLs in an HTML comment beside it. First uses: card 1's
     Azure arrangement and the value chain's Google Finland sentence (both
     "tarkistettu 10/2026"; both page labels stay 9/2026).
   - **Hub English note:** one unobtrusive line under the lede, in English,
     saying the explainer is in Finnish and that the Ecosystem map and Daily
     signals are in English, for visitors arriving from the English
     ecosystem page.
   - **Deviations registry:** the two content changes above alter approved
     text, so they're recorded in `tools/port_deviations.json` alongside the
     earlier intentional ones (the dropped card stepper, the phone row
     labels). `python tools/check_port_text.py --all` applies them and checks
     all 11 pages in one run. A registered text that no longer appears in the
     source is an error, so the registry can't go stale silently.
   - **Known re-check during 2027:** the Microsoft/Fortum waste-heat timeline.
     Recovery from Microsoft's Espoo/Kirkkonummi data centers "begins step by
     step from 2027", per Fortum's May 2026 release. It's on the ecosystem
     page's explanation and case card; see also the content-review reminder
     under the ecosystem page's Phase D entry. Re-verify against Fortum's
     reporting in 2027, and only then bump that page's "Content reviewed"
     date.

   **Second round (2026-10-08, Ray):** header pills lifted, then filled in the
   family blue a step above the page links (variant B of three), clearer links in
   the hub's English note, "tekoäly-yhtiö" spelling, and the hub title and
   kicker shortened. Tracked as R1–R13 in the requested-changes ledger below.

   **Priority from 2026-10-07 (Ray): desktop and laptop first, phone later.**
   Mobile layouts stay functional as built (no sideways page scroll, nothing
   clipped), but get no further refinement until the mobile-polish pass
   below. Batch and change reports lead with desktop/laptop screenshots;
   phone screenshots only when something is actually broken there.

   **Queued rounds, each separate and not yet scheduled:**
   - **Mobile-polish pass across all 11 explainer pages** (queued 2026-10-07).
     Today's phone layouts work but are unrefined. Known candidates: the hub's
     growth-path row wraps awkwardly, the model cards' layer cake is tight at
     360px, and the value chain is a full-size sideways scroll by choice.
   - Switch `ecosystem.html` to `glossary.js`, and fold in its confirmed live
     tooltip bug (49px off-screen at 360px; ecosystem backlog item 3 below).
   - Cross-links from the ecosystem page's nodes into these pages.
   - GPU cloud (neocloud) as its own ecosystem stakeholder.
   - An English version.

   **Known gap:** the hub's layer bars (the "KERROKSET" colour segments) have
   no screen-reader text, the same as the source.

## Requested-changes ledger

Every change Ray asks for gets a row here **before work starts**, quoting his
words, and stays open until it's committed (and live, for changes to rendered
output). The rule is in CLAUDE.md ("Requested changes"). Earlier requests are
recorded in the build-order steps above and aren't back-filled.

**Why it exists (2026-10-08).** Two instructed text changes were acknowledged
and then not applied. Batching wasn't the cause. Both instructions reached the
work by name only, and nothing in the repo recorded what they said:
- "Apply the English-naming change" (2026-10-06) pointed at wording given
  outside this repo. It was guessed at and read as English slugs and glossary
  keys (`109f35d`). The intended change, English labels on the explainer's
  links to English pages, landed only after Ray restated it in full on
  2026-10-07 (`17a616c`).
- The "tekoälyyhtiö" hyphen fix was, per Ray, instructed earlier. It isn't in
  any request that reached this project's working sessions before 2026-10-08
  (checked against the transcript from 2026-10-06 on), so it was never in the
  work queue at all.

The fix has three parts:
- This ledger, so requests are kept in the repo in Ray's words.
- The CLAUDE.md rule: a reference to an earlier request by name is resolved
  against the ledger, or Ray is asked for the original text. Never guessed.
- For approved explainer text, the edit is registered in
  `tools/port_deviations.json` first (`770de66`), so
  `python tools/check_port_text.py --all` fails until it's applied on every
  page.

Status: **open** · **held** (waiting for Ray's approval) · **done** (commit;
live date for rendered changes) · **superseded** · **declined**.

| ID | Date | Request (Ray's words; "…" marks cuts) | Status |
|---|---|---|---|
| R1 | 2026-10-08 | "Lift the header family pills modestly … more contrast against the navy bar, slightly stronger colour or weight, clearer hover and focus. Keep the current shape and the professional feel; no animation. Show at 1680 and ~1280 before committing." | **done:** approved by Ray ("R1: commit and deploy"); `9affcaa`; live 2026-10-08 |
| R2 | 2026-10-08 | "Make the inline links in the English note more visible. … Give them enough contrast to read clearly as links, while keeping the note itself secondary to the Finnish lede." | **done:** `d51fdf3`; live 2026-10-08 |
| R3 | 2026-10-08 | "'tekoälyyhtiö' → 'tekoäly-yhtiö' (hyphen required where the same vowel meets at a compound boundary). This was instructed earlier and never landed. Search all 11 pages and the glossary data; fix every occurrence." | **done:** `1a88537` (hub + five model cards; none in the glossary data); live 2026-10-08 |
| R4 | 2026-10-08 | "Remove 'yhdellä sivulla' from the hub title, leaving 'Datakeskusten liiketoimintamallit'." | **done:** `cf53271`; live 2026-10-08 |
| R5 | 2026-10-08 | "Remove 'ONE PAGER' from the kicker, leaving 'TIEDOT TARKISTETTU 9/2026'." Supersedes "Keep the 'ONE PAGER' kicker as it is" from the same morning's earlier request. | **done:** `cf53271`; live 2026-10-08 |
| R6 | 2026-10-08 | "Changes 3–5 alter approved content: register each in tools/port_deviations.json." | **done:** `1a88537`, `cf53271` |
| R7 | 2026-10-08 | "… the hub title becomes identical to the header brand text directly above it, and the kicker is just the date. Show Ray how that looks and say whether it reads as repetitive." | **done, no change:** Ray: "leave the heading as is. Site name in the header plus page title below is a normal pattern, and making the header differ on one page would be the worse trade." |
| R8 | 2026-10-08 | "Check whether something about how smaller text edits are tracked causes them to be dropped between batches, and fix the cause rather than just making the edit." | **done:** this ledger, the CLAUDE.md rule, `770de66` |
| R9 | 2026-10-08 | "move the interaction tests into tools/ alongside check_layout_sweep.py and check_port_text.py. Keeping them in a temp folder outside the repo is the same failure mode as the dropped instructions, state that matters living somewhere nothing tracks it." | **done:** `503009d` (`tools/check_interactions.py`) |
| R10 | 2026-10-08 | "Note in PLAN.md that explainer changes should run all three checks." | **done:** PLAN.md step 8, "Every explainer change runs all three checks" |
| R11 | 2026-10-08 | "The lifted pills still aren't prominent enough for Ray. Don't commit the current version yet; produce two or three variants side by side at 1680 and ~1280 for him to choose from … A: filled pills (solid background instead of outline), same size as now. B: filled pills, slightly larger than the adjacent in-explainer page links … C: B plus a small group label and separator … Use the existing family blue rather than introducing rust … Keep the icons, and consider slightly larger icon sizing in each variant. Check each variant against the layout sweep … Ray picks." | **done:** Ray picked B ("variant B, thank you"); `b0703f2`, live 2026-10-08. A and C were shown and not built. The lifted version from R1 (`9affcaa`) was live in between. |
| R12 | 2026-10-08 | "Add the one-line pointer to CLAUDE.md: every explainer change must pass all three checks (check_port_text.py, check_layout_sweep.py, check_interactions.py) before committing, with a pointer to PLAN.md step 8 for the commands." | **done:** CLAUDE.md, "Files & deployment" |
| R13 | 2026-10-08 | "Leave the pixel-diff scripts where they are. They're only needed when re-porting from a new design export, so the PLAN.md note is sufficient; moving them would be tidiness rather than risk reduction." | **done, no move:** decision recorded in PLAN.md step 8 |
| R14 | 2026-10-08 | "Model card 1 (Julkinen pilvi), 'TODELLINEN VERTAILUKOHTA' box. The current sentence says Azure has been OpenAI's primary cloud since 2016. That's accurate for 2016 but implies the arrangement is unchanged, which it isn't. Add one short Finnish sentence noting that the relationship became exclusive in 2023 and that OpenAI can now also serve its products through other clouds, while Azure remains the primary cloud. Keep it to one sentence; don't expand the box. … Record the sources alongside the fact, as the financing page does." Register in tools/port_deviations.json, run all three checks, "show Ray the wording before committing." | **done:** `5ab7fc8`, live 2026-10-08. Approved with a refinement (Ray: use "…myös muissa pilvissä, mutta Azure on yhä ensisijainen." instead of "Azure yhä ensisijaisena"; "check it doesn't grow the box beyond what you measured"). **Held:** the refinement adds a line at 1280 (151 to 174px) and at 1584–1616px; "…tuotteitaan muuallakin, mutta Azure on yhä ensisijainen." keeps the ending and the measured size. Ray chose his exact wording: "Accept the extra line at 1280. Precision about contract structures is the explainer's whole point, so don't trade it for 23px; 'muuallakin' is too vague." Two corrections to the brief, sourced: exclusivity began in 2019, not 2023 (Microsoft, 2019-07-22); the cited continuing-microsoft-partnership URL is the 2026-02-27 statement, which kept API exclusivity; exclusivity ended with the 2026-04-27 amendment. |
| R15 | 2026-10-08 | "Check the other four model cards' 'TODELLINEN VERTAILUKOHTA' boxes and the value-chain page for comparable facts that may have moved since September 2026 (particularly the Microsoft–Nebius agreement and the Stargate Abilene arrangement). Report what you find before changing anything beyond card 1; Ray decides whether to update them." | **done:** findings reported 2026-10-08; Ray's decisions are R17. Not changed: Primary Digital Infrastructure stays out of the Abilene chain (Ray: "the diagram is already dense and the point it makes doesn't depend on naming every co-investor"). |
| R16 | 2026-10-08 | "Review date: this is the first genuine fact update since the 'tiedot tarkistettu 9/2026' label was introduced. Don't bump the label globally. Propose to Ray which pages you've actually re-verified, so the date is raised only there." | **accepted** (Ray: "Keep the 9/2026 labels; date the updated facts themselves with 'tarkistettu 10/2026' in the fine print of the pages you actually changed. Don't raise any page label without a full pass of that page's facts."); **done:** "tarkistettu 10/2026" in card 1's and the value chain's fine print (`5ab7fc8`, `3604863`), live 2026-10-08; rule recorded in step 8 under the review-date label |
| R17 | 2026-10-08 | "R15, value-chain page: fix both precision issues you found. … 'yli 13 miljardin' → 'vähintään 13 miljardin', matching Google's 'at least'. The Loviisa clause is factually wrong as written: Google didn't invest in the plant, it signed a 22-year PPA with Fortum supporting the plant's life extension. Reword accordingly." Register, run all three checks, "show Ray the final wording for the value-chain changes before committing, then commit, push and deploy." | **done:** `3604863` (wording), `7589960` (dark-box term style), live 2026-10-08. Wording shown first; "sähkönostosopimus" carries the existing PPA glossary tooltip. Ray: "the value-chain wording is correct as proposed … The dark-panel term styling fix is fine." |
| R18 | 2026-10-08 | "Add 'One paiger' as the first item in the header's top-row page links, before Arvoketju, linking to business-models/. Treat it exactly like the other page links: same styling, same hover and focus states, and the same active-state marking when the reader is on the hub … It appears on all 11 pages via the shared chrome. Check the row still fits across 1024–1680px with the extra item, and on phones in the 'Sivut' menu. If the row gets tight at some widths, report it rather than silently shrinking the other links. Run all three checks, register the new UI string in port_deviations.json if the text checker needs it, then commit, push and deploy." Label read as "One pager" (the design's own name for the hub; "paiger" taken as a typo). | **done:** `3f71078`, live 2026-10-08. Fits from 1024 to 1680px with nothing truncated or wrapped; the tightest width is 1280 (where the inline list appears), 71px to spare, was 149px. Heads the "Sivut" menu on phones. No registry entry needed: the header is rendered by chrome.js, which the text check doesn't read. |
| R19 | 2026-10-08 | Ecosystem page, Relationship explorer (Ray: "boring"): "Restyle the Relationship explorer to match the poster's visual language. The behaviour is fine … only the look is wrong. Give it the same neon-on-dark treatment as the poster illustration: Each stakeholder box gets its own accent colour with a glowing border, using the same posterAccent colours already in ecosystem-data. The small stakeholder icons already used in the 'All stakeholders' list appear in the boxes. Arrows glow in their flow-type colour rather than drawing as thin flat lines. The selected state should read clearly against the rest, as on the poster. Keep the dimmed/highlighted logic, the filters and the side panel as they are." "Plan first; show screenshots at 1680 and ~1280 before committing, since this is a live page." | **done:** `10524c8`, live 2026-10-09 (ecosystem check 93/93 against the live site; check tool `b7d803a`) |
| R20 | 2026-10-08 | "Move the selected-stakeholder detail beside the poster, not below it. … a click produces a visible result in the same glance. Keep the fuller detail below if useful, but something must appear next to the poster immediately." | **done:** `d68ff7d`, live 2026-10-09 (ecosystem check 93/93 against the live site; check tool `b7d803a`) |
| R21 | 2026-10-08 | "Fix the empty 'Click any box to explore.' strip. … Either fold it into the compact card from point 2 (as its default state) or remove it once that card exists." | **done:** `d316d46`, live 2026-10-09 (ecosystem check 93/93 against the live site; check tool `b7d803a`) |
| R22 | 2026-10-08 | "Reduce the weight of the illustration-caveat note. … should stay, but … Make it smaller and quieter: directly under the poster, in fine print, not a panel." | **done:** `d316d46`, live 2026-10-09 (ecosystem check 93/93 against the live site; check tool `b7d803a`) |
| R23 | 2026-10-08 | "Report, don't fix yet: the poster's two known errors … are still only disclaimed, not corrected. Say what it would take to regenerate or edit the image so the caveat can eventually be dropped." Plus: "Run the ecosystem page's checks, and verify nothing on the dashboard or the explainer is affected." | **queued** (Ray, 2026-10-09: "R23, poster image edit: queued, not now. The caveat stays until then."). Reported 2026-10-08/09; recommended a targeted edit of the existing image, then dropping the caveat. |
| R24 | 2026-10-09 | "the 'Data' filter chip filters nothing, since no relationship carries that type. Don't ship a visible control that does nothing. Either remove the chip, or add the genuinely missing data relationships (operator ↔ hyperscaler ↔ enterprise end users exchange data and connectivity; the poster's own legend includes a Data flow type). Recommend which, with reasoning, rather than picking silently: if the relationships are real and belong in the model, adding them is the better fix; if they'd be padding, drop the chip." Also: decisions A, B and C "all confirmed as you chose". | **done:** `64729e0`, live 2026-10-09 (ecosystem check 93/93 against the live site; check tool `b7d803a`). Chose to add enterprise → hyperscaler "Data & workloads" rather than drop the chip |
| R25 | 2026-10-09 | Bug (Ray): "selecting 'Follow the money' shows the poster unchanged, identical to 'Life of a data center', with no highlighting visible. He sees no money flows at all." "Diagnose before fixing … Report the root cause before changing anything." Add check coverage: "stepping through each path and asserting that the expected stakeholders are highlighted at each step, and that the two paths produce different highlight sets." | **done (diagnosis):** root cause `2c99ea5`; fix tracked as R26 |
| R26 | 2026-10-09 | "R25: implement A plus B2 … A: selecting a walkthrough path starts it at step 1 so the poster changes immediately on click. B2: in the money path, draw money arrows over the poster from payer to payee for each step, in the capital/financing colour, clearly distinguishable from the poster's own printed arrows. The card lists the same payer → payee pairs as text, generated from the same data … The six payer/payee sets you drafted are approved as listed. They're new content: show Ray the final wording of the card's text before committing." "Also fix the direction convention where it states something false … starting with waste heat; report any others you find rather than fixing them silently." "Extend check_ecosystem.py to cover the new behaviour: selecting a path immediately highlights something, the two paths produce different highlight sets, and the money arrows render for each money step." Working rule for this round: "don't hold on screenshot approval unless something is a genuinely new visual direction … Report what you did afterwards, with screenshots included for reference rather than as a gate. The existing CLAUDE.md approval rules still apply to new user-facing text and to changes in behaviour." | **done:** `384bb64` (path starts at step 1), `75b4c28` (money arrows + card), `17fdfe0` (checks); live 2026-10-09, ecosystem check 101/101 against the live site |
| R27 | 2026-10-09 | "Confirm the step text above the card still carries the electricity nuance (bought via a supplier or the market; the PPA fixes price with a producer) … If it is [compressed], restore the nuance there." "Fix the 'Lease & services (compute capacity)' direction in this round … Check whether any other relationship has the same problem and report, rather than fixing silently." "Then commit, push, deploy and verify live." Also: "Where earlier reports in this project cited hashes, treat those as unverified unless they appear in actual command output." | **done:** `eea5c4a`, live 2026-10-09. Money step 4's text now says the PPA fixes the price (the sentence had never said it; unchanged since 2026-09-22). Leased capacity now runs operator → hyperscaler. Audit of all 18 relationships: no other one states a false direction; the poster's own printed lease and waste-heat arrows have heads at both ends. Hashes cited in earlier reports in this project count as unverified unless they appear in command output. |
| R28 | 2026-10-09 | PART A, dashboard history persistence, "Report and propose only; change no code." "1. Confirm or refute: deploy.yml has no cache, artifact download or commit-back, scores_history.json and audit_log.json are gitignored, so every CI run starts with no history; load_scores_history() returns [], and _confirmed_color() always takes the 'unconfirmed (insufficient history — building baseline)' branch. Show the evidence, including how many real (non-'none') days the live dashboard's embedded HISTORY contains. 2. If confirmed, list every live behaviour affected … 3. Recovery: check Actions log retention and whether past scheduled-run logs contain per-sub-layer scores and per-ticker sub-scores (accel, constraints, smart). If they do, say how much history could be rebuilt for analysis. Don't seed the live file from it. 4. Propose a persistence fix. Compare a dedicated data branch with commit-back, restoring from the previous deploy, and actions/cache. Cover durability, what happens on a failed restore (it must fail loudly, never silently start fresh), permissions, and races. My preference is the data branch; argue against it if you think it's wrong. 5. Include in the same proposal a fix for _load_recent_layer_scores' .get('score', 0): a missing day must be excluded and noted, never counted as 0 (decision #6), since it could falsely confirm Blue. 6. State how activating confirmation will change live colours. This needs my approval and a before/after check under CLAUDE.md. 7. Correct PLAN.md (doc only, commit by path): step 7's claim that multi-day data 'will accumulate once scheduled runs begin', the heat-trail 'confirmed by code review' statement, and add to Open question #1 that no multi-day history has been collected since launch." | **decided** 2026-10-10: see R30 (disclosure), R32 (snapshot), R33 (persistence) and R34 (PLAN.md) |
| R29 | 2026-10-09 | PART B, ecosystem page: "1. In money step 1 a € badge covers the poster's 'Lease & services (compute capacity)' label. Place badges so they never cover printed poster labels; add a check for overlap with label boxes if practical. 2. The explorer has no operator ↔ enterprise relationship, although the poster draws one and money step 1 charges 'Enterprise → Operator: colocation fees'. Recommend whether to add it (e.g. operator → enterprise, colocation space, power and cooling), with type and wording. Show me the wording before committing; it's new user-facing text. 3. On a fresh load, check that clicking the already-active 'Life of a data center' chip starts step 1. If it doesn't, fix it and add the case to check_ecosystem.py." "Run the four checks, verify live after deploy, quote hashes only from command output." | **B1/B3 done** (`ac197b2`, `b49c2ce`, live 2026-10-10); **B2 approved** with an extended explanation, see R31 |
| R30 | 2026-10-10 | "1. Disclosure (ship first, on its own). Render the note _confirmed_color() already returns on each sub-layer card, so the disclosure stays correct by itself once persistence is live. While any sub-layer is unconfirmed, add one page-level line, e.g. 'Colours currently reflect a single day's reading; multi-day confirmation isn't active yet.' Show me the exact page line and every note variant before committing." | **done** with R36's changes: `e047238`, live 2026-10-10 (all five cards show the insufficient-history note, plus the page line); wording superseded in part by R42 (session, not 'today') |
| R31 | 2026-10-10 | "2. R29: approved, with this explanation (label unchanged): 'Businesses rent space in the operator's facility for their own servers, usually racks or a cage in a shared hall (retail colocation), with power and cooling supplied by the operator and often direct connections to carriers and cloud providers in the same building.'" | **done:** `b1f3b34`, live 2026-10-10 (ecosystem check 103/103 against the live site) |
| R32 | 2026-10-10 | "3. Read-only snapshot before building persistence: a. Run the pipeline locally once (weekend, so Friday's full bars) and give me per ticker: accel, constraints, smart, composite, fund_delta, and whether accel×0.65 + smart×0.15 ≥ 45. b. For the 15 recovered days: which run per day you used, and for days with several runs, the spread of each sub-layer's score within the day." | **done:** reported 2026-10-10 (local run on Friday's full bars; per-ticker table; per-day runs and within-day spreads) |
| R33 | 2026-10-10 | "4. R28 persistence: data branch approved, with these changes: a. Split the workflow: build/deploy keeps contents: read; a separate small job with contents: write receives only the two files (as an artifact) and pushes them to the data branch. b. Instead of 'weekday scheduled runs only': date each history and audit entry by the last completed US market session, not the wall clock; the last run for a session overwrites earlier ones. First verify, on a run during US trading hours, whether t.history(period='6mo') includes today's unfinished bar. If it does, drop it: vol_spike = volumes[-1]/vol_avg otherwise depends on when GitHub fires the cron. Report how many of the 15 recovered days came from intraday runs. c. Audit log on the data branch: one entry per ticker per session, no 500-entry cap, including accel/constraints/smart and fund_delta. This is the data the Red-threshold question needs. d. Missing-day fix as you proposed: excluded and named, never 0; days older than 7 calendar days excluded; an unreadable file in CI is an error. e. Commit the 15 rebuilt days and the raw run logs to the data branch under archive/, never read by the pipeline, before the logs expire. f. Confirm that a failed scheduled run actually notifies me. g. Activating confirmation: approved, with the before/after check on live per CLAUDE.md. Report the notes from the first live runs." | **in progress:** e done (data branch `1bc7b92`, archive/); **f closed** (R39): GitHub's "Run failed" email arrived for the 10:23 UTC test run (38044696377), so failure emails reach Ray; the failure issue job (`ceb1e22`) runs as well. Known gap: a run whose job never gets a runner (2026-10-05) sends neither (Known issues, "Runs that never start"); b: 13 of 15 recovered days were intraday runs; **b and d committed** (`4d9eeb1`, tests `03b7466`), live at Monday 2026-10-12's scheduled run, which is the before/after check (before: `Output/before_after_r42/`); Monday's log also shows whether yfinance returned an unfinished bar (each dropped bar is logged); a, c, g to build. d's tests must include a weekday session with no entry because its run never started (the 2026-10-05 case): excluded, named in the note, never 0 (R39) |
| R34 | 2026-10-10 | "5. PLAN.md, doc only: a. Add a lesson: the parent's commit-back step both published index.html and persisted history; the Actions-based deploy replaced the first and dropped the second. Before replacing a parent mechanism, list everything it did. b. Add to the open queue, to carry over to the parent's own session (don't change AI_valuechain from here): its _load_recent_layer_scores has the same .get('score', 0), and there the history persists, so the bug is live. Its 06:00 UTC run dates yesterday's session as today, and its 20:30 UTC run falls before the US close after 1 Nov (close is 21:00 UTC in winter), so the session-dating fix applies there too." Plus: "Run the four checks, verify live after each deploy, quote hashes only from command output." | **done:** `b5bc8b5` |
| R36 | 2026-10-10 | R30 changes: "1. Show the page line only while at least one card is in the insufficient-history branch, not 'while any sub-layer is unconfirmed'. After persistence goes live, 'not sustained' cards must not trigger it. Wording: 'Colours are based on today's reading only; multi-day confirmation starts once a few days of history are stored.' 2. Make the notes plain, once, inside _confirmed_color() (so the page follows the data). Proposed wording; adjust only where it would be inaccurate: insufficient history: 'Today's reading only — not yet confirmed (N of 2 earlier days stored)'; instant Red, score: 'Red without waiting: score {x} is above 80'; instant Red, delta: 'Red without waiting: the leading company's revenue growth is accelerating sharply'; confirmed: '{Colour}, confirmed: {n} of the last 3 days also {above/below} {t}'; holding: 'Kept {Colour}: today's score {x} is near the line, and recent days were mostly {Colour}'; not sustained: 'Shown as {displayed colour}: today's {x} hasn't held over recent days'. Show me the final strings and screenshots, then commit, deploy and verify live. R31 follows as planned." R33: "3. Build session dating defensively now: drop any bar dated today in US/Eastern unless the session has closed, and date entries by the last completed session. Monday's trading-hours run then verifies it; it doesn't decide it. 4. Add a final workflow step that opens a GitHub issue when the run fails (on top of email, which I'll confirm separately)." | **1–2 done:** `e047238`, live 2026-10-10. **4 done:** `ceb1e22` (see R38). **3 committed** `4d9eeb1` with R42's decision (prices, the day's move and VIX from completed-session bars), live at Monday 2026-10-12's scheduled run, which is the before/after check (before: `Output/before_after_r42/`). Note wording superseded in part by R42 |
| R35 | 2026-10-10 | "R35, new, read-only, before any weight change: 5. The R32 snapshot suggests the 65/20/15 weights cap the constraint signal at 20 points, so optical (constraints 70–100) can't get past ~52. Before proposing anything, check the inputs: a. Constraints: for COHR (100.0), LITE (90.1) and CIEN (87.7), list the headlines and keyword matches behind the score. Is 100.0 a cap being hit? Does keyword purity hold (no bare names or tickers)? Are headlines layer-filtered? b. Smart money: why it is 0.4–19.6 for all 12 tickers. Show each component per ticker (volume-price, analyst, short interest), which are None or missing, and how missing values are handled. If missing is scored as 0, that breaks decision #6: report it, don't fix it yet. c. Only once a and b are clean: show what composite and colour each sub-layer would get under 2–3 alternative weightings, against today's snapshot and the 15 recovered days. No proposal or change to the live weights; that needs my approval and a before/after check." "Quote hashes only from command output." | **a, b reported** 2026-10-10 (not clean; findings under Known issues, "Scoring inputs"). **c held** until a and b are clean |
| R37 | 2026-10-10 | "Amend the parent carry-over note in PLAN.md (item 5b of my last instruction), doc only, commit by path: Replace the point about the 20:30 UTC run falling before the US close after 1 Nov. The parent's bot commits show its crons fire 4–7 hours late (morning ~10:30–13:25 UTC, evening ~23:00–01:20 UTC). Consequences: the evening run sometimes lands after midnight UTC, so a date's entry holds either that day's or the previous day's session; a Friday evening run can write a Saturday entry (2026-10-10 00:08 UTC), counting Friday's session twice; the 2026-10-05 morning run committed at 13:25 UTC, minutes before the US open. Verify these from `git log --author=bot` in the parent before writing them down." | **done:** `58479cd`. Two points corrected on verification: the evening cron fires 2.2–4.8 h late, not 4–7 h; Friday 2026-10-09's session is in one entry so far (the Saturday one), since Friday's own entry holds Thursday's. The double counting comes from Monday-morning entries (2026-09-28, 2026-10-05) |
| R38 | 2026-10-10 | "R33.f: I received no email for the 2026-10-05 run. Treat the report-failure issue job as required. When you run its deliberate test failure, tell me the time so I can check whether an email arrived too." | **done:** `ceb1e22` (job `report-failure`, plus a manual-only `test_failure` input). Tested 2026-10-10: run 38044696377 failed on purpose at 10:23:05 UTC, and issue #1 opened at 10:23:09 UTC, assigned to miikawir-ops (closed afterwards as a test). Normal run 38044762500 skipped the job and deployed, live 10:24 UTC. Tested on main, not a throwaway branch: the github-pages environment only allows main. GitHub's "Run failed" email for that run arrived (Ray, R39) |
| R39 | 2026-10-10 | "R33f: I received GitHub's 'Run failed' email for the 10:23 UTC test (Deploy RayDar Data Center dashboard, main, ceb1e22). Failure emails reach me. Close R33f with that recorded. Record as a known gap: the 2026-10-05 run was marked failed but its job never started, and I got no email for it. Check whether report-failure (if: failure()) would fire in that case; if not, say so in PLAN.md. The detection for that case is R33d's missing-day note, so include it in R33d's tests as already asked." | **done:** `e50568a`. `report-failure` wouldn't fire: the job's result was `cancelled`, not `failure`, and the job never got a runner, which the report job also needs |
| R40 | 2026-10-10 | "R33d: expected sessions from trading dates approved. Take them from a reference series every run fetches (e.g. ^GSPC daily bars); if that fetch fails, the run fails loudly, never 'no sessions expected'. R33d addition: include a test where a scheduled session is missing entirely (e.g. a run that never started, like 2026-10-05) and show that the card note names the missing day." | **committed** `4d9eeb1` (tests `03b7466`) with R42's wording, live at Monday 2026-10-12's scheduled run, which is the before/after check (before: `Output/before_after_r42/`). Built 2026-10-10 and held for Ray's approval of the note wording ("(no reading for Mon Oct 5)"). `tools/check_confirmation.py` 28/28, including the 2026-10-05 case end to end through stage_score() and the rendered card. Open with it: the card's "vs yesterday" delta compares against the latest stored session, so with Mon Oct 5 missing it compares Tue Oct 6 with Fri Oct 2 under the same label |
| R41 | 2026-10-10 | "R33.3 addition: the bar helper must also drop any trailing row whose Close is NaN, regardless of its date, and any NaN that still reaches a computed value must become None and be named in data_missing (decision #6), never written to the page. Evidence: the parent's published page has "ret30": NaN for all 28 tickers on almost every run after 00:00 UTC (e.g. 10-10 00:08, 10-09 00:32, 10-08 00:17) and on none before midnight; likely an empty last bar. Add a test with a trailing NaN row. Also add this to the parent carry-over queue." | **committed** `4d9eeb1` (tests `03b7466`), live at Monday 2026-10-12's scheduled run, which is the before/after check (before: `Output/before_after_r42/`). `tools/check_confirmation.py` 41/41, including a trailing NaN row dated a past session (fails on the previous helper). Found on the way: before the clamp check, a NaN close made momentum +5, the maximum. Carry-over entry added; one correction to the evidence: one morning run (2026-09-23 10:40 UTC) also has NaN |
| R42 | 2026-10-10 | "R40 and R41 approved with these changes. Log them in the ledger with my words. 1. Wording: scores now belong to the last completed session, not 'today'. Page line: 'Colours are based on the latest session's reading only; multi-day confirmation starts once a few sessions of history are stored.' No history: 'Latest session only — not yet confirmed (1 of 2 earlier sessions stored; no reading for Mon Oct 5)' Confirmed: 'Orange, confirmed: 2 of 2 available recent sessions also at or above 40 (no reading for Mon Oct 5)'. Use 'N of M available recent sessions' whenever a session is missing, and 'N of the last 3 sessions' otherwise. Holding and not sustained: as proposed, but 'latest score' instead of 'today's'. Several missing: as proposed. 2. Score delta: always label it with the comparison session's date ('vs Fri Oct 9'), never 'vs yesterday'. 'Yesterday' is wrong on every Monday and after holidays, not only after a missing session. 3. Data date: next to 'Fetched…', show the session the scores belong to, e.g. 'Data: close of Fri Oct 9 · fetched 18:24 UTC'. 4. R36 item 3 decision: price, the day's price move and VIX come from the kept completed-session bars like everything else; show the price with its session date. No live intraday quote anywhere in scoring or on the cards. Show me the final note strings and one screenshot, then commit R40/R41 code and the test tool separately and push. Monday's scheduled run is the before/after check on live; report it." | **committed** `4d9eeb1` (code), `03b7466` (tests, 57/57); strings and screenshot shown 2026-10-10. Accuracy adjustment: "N of M available recent sessions" is also used when fewer than 3 sessions are stored without a gap (the first days of a history), so a note never implies a session was checked that wasn't. Market cap is Yahoo's rescaled to the session close (shares x close is wrong for DELL: one share class). live at Monday 2026-10-12's scheduled run, which is the before/after check (before: `Output/before_after_r42/`) |
| R43 | 2026-10-10 | "1. Wording: use 'recent sessions' instead of 'recent days' in the holding and not-sustained notes, for consistency. 2. Fix both minor items now: the header shows 'UTC' with its time, and the sparkline date labels count back from the session date, not the viewer's date. Update check_confirmation.py. 3. Commit by path and push, then trigger a manual workflow_dispatch run now (not test_failure). It scores Friday's close, the same session as the saved 'before' from Saturday 10:24 UTC, so compare the two: price-based inputs should be identical, and separate any score change into news vs code. Verify live (root, ecosystem, business-models hub), check the page text for NaN, and report. 4. Monday's scheduled run remains the trading-hours check (R33b): report whether an unfinished bar was dropped. Log in the ledger; quote hashes only from command output." | **1-3 done:** `1824399` (code), `d91ff1a` (tests, 62/62); manual run 38068453210, live 2026-10-10 16:38 UTC (root, ecosystem, business-models hub 200; no NaN, no 'vs yesterday', no "today's" in the page text). Sparkline labels are each point's own session date (sampled back from the session's bar) rather than counted back from it, so they can't drift. Before/after on the Fri Oct 9 close: price-based page fields identical except SMCI price 41.85 -> 41.86 (live quote -> official close) and 52-week highs rounded (VRT 379.935 -> 379.93, ANET 217.4099 -> 217.41). Networking 38.3 -> 39.5 is news (5.0 -> 6.0 hits). Code effect: zero, old (`ceb1e22`) vs new code on the same inputs and news, in both the local and CI's package versions (within 0.0001). Optical 43.6 -> 43.7: not news (10.0 both) and not code; the run's own inputs put it at least 0.01 higher, which crossed the rounding line; per-ticker inputs aren't kept in CI, so the input can't be named (R33c will keep them). Found on the way: CI installs yfinance 1.7.0, not the local 1.4.0 (Known issues). **4 open:** Monday's scheduled run |
| R44 | 2026-10-10 | "Pinning approved; do it first, before Monday's run, as its own commit: Pin every dependency in requirements.txt to the exact versions CI installed in run 38068453210 (yfinance 1.7.0, pandas 3.0.6, and the rest). Pin to CI's versions, not your local ones. Update your local environment to the same pins and re-run the four checks and check_confirmation.py on it. Add a check to the pipeline that fails loudly if an expected column or field is missing from yfinance data (e.g. the analyst source), so a future version change can't silently return 0 again. Log in the ledger, commit by path, push. No deploy needed; Monday's scheduled run picks it up." | **done:** `356ea61` (requirements.txt: all 25 packages CI installed, exact versions), `7976ff9` (.venv ignored), `e9e3fc8` (data-format check), `399d305` (tests). Local environment: a project `.venv` with the same 25 pins (plus Playwright and tzdata for the checks and Windows time zones); only Python differs (3.14 locally, 3.12 in CI; 3.12 isn't installed here). On it: check_confirmation.py 71/71, and the four checks pass. One deviation, to be confirmed by Ray: the analyst column is already missing, so a strict check would fail every run until R45 ships; it's logged as an error on every run instead (KNOWN_FORMAT_BREAKS), and nothing else may be added there. Live with Monday's scheduled run |
| R45 | 2026-10-10 | Row A, "input correctness (scoring change: replay first, then my approval, then a live before/after): 1. Analyst: score as missing (None, named in data_missing) when the expected data isn't there; read per-action grades from upgrades_downgrades if that's the correct source in yfinance 1.7.0. 2. Momentum: fix the sign when both returns are negative, the near-zero 90-day case, and the 5-day window. 3. News: count each story once across feeds; a ticker-feed headline counts only if it names that company; remove the bare-brand +1 for generic headlines (CLAUDE.md topical rule); generic headlines count for a sub-layer only through terms specific to that sub-layer, not the shared supply keywords. 4. Every history and audit entry carries a model_version, bumped whenever scoring inputs, formulas or weights change. Replay each fix separately on the 2026-10-09 session, plus all together, on the pinned versions. Show per ticker: before, after, and which fix moved it. Ship them together as one release, not before Monday's R33b check is reported." | **open** |
| R46 | 2026-10-10 | Row B, "design questions (proposals only, no change): a. Capex/operating cash flow measures cash-flow strain, not supply constraint (COHR 8.1 because cash flow is small). Propose an alternative (e.g. capex growth year on year, or capex/revenue) and show its effect. b. Short interest: I'm inclined to score it as missing until it has a defined meaning. Check whether yfinance gives a prior-month figure, so a change could be used instead of a level. c. R35c (alternative weightings) runs after Row A is live." | **open** |
| R47 | 2026-10-10 | "Parent carry-over queue: add that AI_valuechain has the same momentum formula (fetch_market.py:311), the same 'To Grade' analyst check (:380) and an unpinned yfinance (>=0.2.40). Queue: run_rate is null for all 12 tickers (revenue_quarterly filled only on a fallback path). Quote hashes only from command output." | **open** |

## Queue (this project)

Queued work that isn't a ledger request in progress.

- **Run rate never shows (ledger R47).** `run_rate` is null for all 12
  tickers on the live page: `fetch_ticker_data()` fills `revenue_quarterly`
  only on the fallback path (when the quarterly revenue growth can't be
  computed), so the cards' "Run rate $XB/yr" line never appears. Found in the
  R35 check (Known issues, "Scoring inputs").

## Queue: carry over to the parent's own session (AI_valuechain)

Found here, to be checked and fixed in the parent's own session; nothing in
AI_valuechain is changed from this project (ledger R34, 2026-10-10). As
reported by Ray. Not verified from here: per CLAUDE.md, `reference/` is a
copy and says nothing about the parent's live code.

- **Missing day counted as score 0 in colour confirmation.** The parent's
  `_load_recent_layer_scores()` has the same `.get("score", 0)` as this
  project's. There the history does persist, so the bug is live: a sub-layer
  missing from a day's history counts as a 0, i.e. below 30, which can
  falsely confirm Blue (and counts against Red/Orange confirmation). Fix as
  here (ledger R33d): a missing day is excluded and named, never 0.
- **History dated by wall clock, not by US market session.** The parent
  keeps one history entry per UTC date; the last run that date overwrites
  it. Its crons fire late. Between 2026-09-14 and 2026-10-10, the 06:00 run
  started 4.4–7.4 hours late (10:26–13:24 UTC) and the 20:30 run 2.2–4.8
  hours late (22:41–01:20 UTC); each bot commit followed 1–3 minutes after
  its run started. Verified from `git log --author=bot`, the Actions run
  list and `scores_history.json` at `170ab49` (ledger R37):
  - The morning run lands before the US open, so it records the previous
    session under today's date. On 2026-10-05 it committed at 13:25 UTC,
    five minutes before the open.
  - Since 2026-09-28, 7 of 10 evening runs landed after midnight UTC and
    wrote the next date's entry. A date's entry therefore holds either that
    day's session (evening run before midnight) or the previous day's
    (morning run).
  - Sessions get recorded twice or not at all. Friday's session sits in
    both Friday's and Monday's entries (2026-09-25 and 09-28; 2026-10-02 and
    10-05), and Tuesday 2026-09-29 and 2026-10-06 each appear twice. Monday
    2026-09-28, Thursday 2026-10-01 and Monday 2026-10-05 are missing: their
    after-midnight entries were overwritten by the next morning's run.
  - The Friday evening run wrote a Saturday entry (2026-10-10, 00:08 UTC)
    holding Friday 2026-10-09's session; Friday's own entry holds
    Thursday's.
  - Fired on time, the 20:30 run would fall before the US close once
    daylight saving ends on 1 November (21:00 UTC in winter).
  The session-dating fix (ledger R33b) applies there too.
- **NaN 30-day returns on the published page (ledger R41).** Verified from
  the parent's `index.html` in its bot commits: `"ret30": NaN` for all 28
  tickers on 6 of the 7 runs that landed after 00:00 UTC (2026-09-29 to
  2026-10-10; all but 2026-10-02 00:02), and on one morning run
  (2026-09-23 10:40 UTC). None of the evening runs that landed before
  midnight has it. `ret_1mo` and `ret_3mo` are NaN on the same pages; all
  three use the last close, which fits an empty (NaN) last daily bar. That
  cause is inferred, not observed. Code read at the parent's HEAD:
  `fetch_market.py` takes `t.history(period="6mo")` without dropping such a
  row, and clamps momentum with `max(-5.0, min(5.0, m))`, which turns a NaN
  into +5.0; `score_engine.py` scores +5.0 as 80. Its effect on the
  parent's scores on those runs wasn't measured from here. Fix as here
  (ledger R41): the bar helper drops trailing NaN rows, momentum is checked
  for NaN before the clamp, any NaN left becomes None and is named in
  `data_missing`, and the page refuses NaN.
- **Same scoring-input defects and unpinned dependencies (ledger R47).**
  Verified at the parent's HEAD (`170ab49`): `fetch_market.py:311` is the
  same momentum formula as here before ledger R45 (the ratio of the 5-day
  return to a ninetieth of the 90-day return, so two negative returns make
  a positive momentum and a near-zero 90-day return saturates it; clamped
  to ±5 at :313; its "5-day" return at :309 spans 4 sessions). :380 is the
  same "To Grade" check on `t.recommendations`, which yfinance 1.4 and 1.7
  return as a monthly summary table without that column, so analyst
  upgrades are always 0; there, a failed fetch is also scored 0
  (`except: analyst_upgrades = 0`). `requirements.txt` has
  `yfinance>=0.2.40`, with pandas and numpy unpinned too. Fixes as here:
  pinning (ledger R44), and the input fixes in ledger R45 once they're
  approved.

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

- **Runs that never start aren't reported (ledger R39).** The 2026-10-05
  scheduled run (37367980773, created 20:09 UTC for the 12:00 cron) is
  marked failed, but its only job never got a runner: the job's result is
  `cancelled`, it has no steps, and its annotation reads "The job was not
  acquired by Runner of type hosted even after multiple attempts". Ray got
  no email for it, although failure emails do reach him (the 10:23 UTC test
  on 2026-10-10). The `report-failure` job wouldn't have fired either, for
  two reasons:
  - It runs on `if: failure()`, which is true only when a job it depends on
    failed. Here that job was cancelled. (The job result is from the API;
    how `failure()` treats a cancelled job is GitHub's documented behaviour,
    not tested here.)
  - It needs a hosted runner itself, which is what was missing. Widening the
    condition to catch cancelled jobs wouldn't make it reliable, and would
    also open issues for runs cancelled on purpose.
  Detection for this case is R33d's missing-day note: the next run names
  the session that has no entry. R33d's tests include it.

- **Unpinned requirements (ledger R43).** `requirements.txt` lists
  `yfinance` and `feedparser` without versions, so each CI run installs the
  latest: on 2026-10-10 yfinance 1.7.0, pandas 3.0.6, numpy 2.5.3, against
  yfinance 1.4.0 locally. Prices come back at slightly different precision
  (LITE's Friday close: 1103.355 on 1.7.0, 1103.35 on 1.4.0). Re-checked on
  1.7.0: "Adj Close" still equals the default adjusted close, and
  `recommendations` is still the summary table, so the R35 analyst finding
  holds on CI's version. Pinning is a dependency change and needs Ray's
  approval; until then, CLAUDE.md says to check the CI versions before
  treating a local run as evidence of live behaviour.

- **Scoring inputs (ledger R35, read-only check 2026-10-10).** Reported to
  Ray, not fixed. Local run on Friday's full bars; data in
  `Output/r35_inputs_2026-10-10/`.
  - *Analyst upgrades are always 0 (decision #6 break).* yfinance 1.4.0's
    `recommendations` is a monthly summary table (`period, strongBuy, buy,
    hold, sell, strongSell`) with no "To Grade" column, so
    `analyst_upgrades` stays 0 for all 12 tickers and is never flagged
    missing. It carries 25% of smart money. Per-action grades are in
    `upgrades_downgrades` (column `ToGrade`).
  - *Momentum.* When the 5-day and 90-day returns are both negative, the
    ratio comes out positive: VRT (−4.3% over 5 days, −20.0% over 90) scores
    56.9 of 100. A 90-day return near zero saturates the ratio at ±5: EQIX
    (+0.3% on +0.7%) scores 80.
  - *Short interest* is a level (`shortPercentOfFloat` − 5%), not a change,
    and scores higher the more of the float is shorted.
  - *Constraints news.* The 20-point news cap hides the size of the optical
    count (28 points). Two headlines are counted twice (the same story in
    two feeds of one sub-layer). Five of 27 counted headlines don't name
    the company whose feed they came from. DLR's press-release boilerplate
    contains "colocation". Generic headlines still count on a bare brand
    name (none did on 2026-10-10).
  - *Unused field.* `revenue_quarterly` is only filled on the fallback path,
    so the cards' "Run rate" line never shows (`run_rate` is null for all 12
    tickers on the live page).

- **`ecosystem.html` — poster-primary redesign (Phase C, 2026-09-22).**
  Ray: the poster "looked far better than the plain SVG map" — restored
  it as the primary, now-interactive view, with the SVG map demoted to a
  secondary "Relationship explorer" tab. Single source of truth is now
  `ecosystem-data.v2.js` (bumped from v1 — content changed: added
  `posterBox`, `POSTER_GROUPS`, `PANEL_REGION`). `posterBox {x,y,w,h}`
  (% of `assets/ecosystem-v2.webp`, 1536×966) was measured directly off
  the image — crop+zoom each region, read pixel edges — not estimated;
  Playwright screenshots at 1850px/1280px confirmed the resulting hotspot
  buttons align with the illustrated boxes.

  **TSO/DSO share one poster hotspot.** The source poster has a single
  "Grid & Transmission (TSO)" box — no separate DSO box exists to
  measure. `POSTER_GROUPS.tso` folds `dso` into `tso`'s `posterBox`;
  clicking it opens a combined panel with two labeled sub-sections
  ("TSO (Fingrid)" / "DSO (e.g. Caruna)" — the Finland hedge on DSO
  matters, there are many). `tso`/`dso` stay fully separate everywhere
  else (Relationship explorer, mobile accordion).

  **Multi-highlight dimming uses an SVG `<mask>`** (`#poster-dim-mask`),
  not a single-exclusion overlay — a base white rect dims the whole
  poster, and one black cutout rect per active `posterBox` is added/
  removed as the highlight set changes. This is what lets the walkthrough
  and case card (which highlight several stakeholders at once) light up
  multiple boxes simultaneously on the poster; verified via screenshot
  showing all 5 poster boxes lit for the 6-stakeholder case-card set
  (`tso`+`dso` collapse to one box). Hotspot glow ring reuses the
  parent's "Enter RayDar Data Center ↗" glow language (same two colors,
  `rgba(133,183,235,·)` / `rgba(83,74,183,·)`, same base/hover intensity
  split), adapted from a filled button to an outline ring since hotspots
  sit on top of the photo rather than having their own background.

  **The real "Selected stakeholder" panel always renders below the
  poster, not as an overlay on top of it.** The original plan called for
  an on-image overlay positioned over the illustration's panel region,
  falling back to below only if that region rendered narrower than
  ~320px. Verification found the fallback is the *only* reachable state:
  `.poster-frame` is capped at `max-width:1536px` (the image's native
  size), so `PANEL_REGION.w` (20.4%) tops out at ~313px at any viewport
  width — confirmed 313px at 1850px and 248px at 1280px, both under the
  threshold. Rather than ship dead overlay code, the overlay/below
  branching and the resize-driven width measurement were removed
  entirely; the panel always renders in `#panel-below`. A static
  `#panel-cover` (no JS, no width logic) sits over the illustration's
  fake panel region instead, reading "Click any box on the map, details
  appear below ↓" — hides the non-functional baked-in panel and points
  at where the real one lives.

  **Mobile (<768px): static poster image, no hotspots, no toggle, the
  accordion directly underneath.** The view toggle is hidden below
  768px (poster and explorer would show the same accordion content
  either way), and the accordion (`#mobile-list`) was moved out of the
  explorer's markup to a top-level element between the two views — one
  generator function populates it regardless of which view is "active,"
  so mobile and desktop can't drift apart into two different stakeholder
  lists. `#panel-below`'s "click a box" placeholder is also hidden on
  mobile (misleading once hotspots are gone — the accordion is the real
  interactive element there).

  **All three original image-era issues remain resolved by
  construction** (same mechanism as Phase B, now serving the poster
  hotspots too): `FLOW_TYPES` defines relationship colors once for the
  map, legend, side panel, *and* poster panel; every supplier category
  has exactly one stakeholder node; the "Selected stakeholder" panel is
  real. The poster's own two remaining illustration issues (arrow-color/
  legend mismatch on waste heat and backup power & fuel; three suppliers
  shown both standalone and inside "Equipment & Technology Suppliers")
  are called out in a short note under the poster, same as before.

  **Explorer-tab layout fixes**: edges now clip to each node's box
  border instead of terminating at its center (`boxEdgePoint()`), so
  lines stop at the edge instead of drawing through boxes; dimmed
  opacity raised from 0.12/0.3 to 0.45; side panel gets `max-height` +
  scroll so it can't overflow the viewport; viewBox padded
  (`-20 -20 1040 740`) against edge clipping.

  **Deliberate additions beyond the original image**, unchanged from
  Phase B, still flagged in `ecosystem-data.v2.js` with `added: true`:
  `dso↔operator`, `hyperscaler→enterprise`, `energy_gen→tso`,
  `tso→dso`, `capital→construction`.

  **Verified with a real headless browser (Playwright/Chromium)**,
  installed locally and removed after (not a project dependency): two
  full passes. First pass covered hotspot alignment at 1850px/1280px
  (screenshots with hotspots outlined), multi-cutout dimming, the
  combined TSO/DSO panel, walkthrough/case-card poster highlighting,
  keyboard selection (Tab+Enter, focus-visible), the view toggle, and
  the original mobile accordion path — all passed, which is what
  surfaced the overlay-panel and mobile-accordion findings above. A
  second pass re-verified after fixing both: panel-cover text and
  positioning at both widths, combined-panel content still correct with
  panel-below as the only path, and mobile confirmed toggle/explorer/
  hotspots/cover all hidden, accordion visible immediately after the
  poster and functional on tap. Zero JS console errors throughout.

- **`ecosystem.html` — bug fixes, light-card redesign, hero, and six
  E-items (Phase D, 2026-09-22).** Data file bumped to
  `ecosystem-data.v3.js` (content change: `posterAccent`, `GLOSSARY`,
  `MONEY_WALKTHROUGH_STEPS`, `CONTENT_REVIEWED` added).

  **Real bug found and fixed, diagnosed against the live URL before any
  fix was proposed** (per Ray's explicit ask): clicking a poster hotspot
  directly always worked — verified with Playwright against the actual
  deployed page, not just localhost. The real, reproducible gap was that
  the walkthrough and case card (`highlightSet`, not `selectedStakeholder`)
  lit up boxes but left the panel on its generic placeholder — confirmed
  live via a scripted "click Next" that produced correct glow with zero
  panel explanation. Fixed by giving the panel a third state: a
  "Currently highlighted" summary when `highlightSet` is active with no
  specific selection, in addition to the selected-stakeholder and empty
  states. This also explains Ray's "dimmed by default" report — a
  walkthrough step left mid-way (not literally the default -1 state) was
  correctly dimmed but visually unexplained.

  **Selected-state dim opacity** lowered `rgba(8,8,20,0.55)` →
  `rgba(8,8,20,0.32)`; default (no selection) state confirmed at zero
  dimming both before and after (mask `display:none`), so what read as
  "dimmed by default" live was the bug above, not the base state.

  **Panel redesign**: the covered illustration region (formerly a static
  dark cover) is now a real light card (`#compact-card`) — white
  background, dark text, 5px top accent stripe in the clicked
  stakeholder's own `posterAccent` color (sampled directly from the
  poster image's neon border per stakeholder, same measure-don't-guess
  approach as `posterBox`), relationship chips with flow-type dots (a
  thin `rgba(0,0,0,.18)` outline keeps pale dots visible on the light
  background), default state shows a small cursor icon + "Click any box
  to explore," and a single 90ms opacity fade on content swap (no
  continuous animation, per spec A5). Verified legible at both 1850px
  (~313px wide) and 1280px (~248px wide) via screenshot — narrower than
  what killed the original overlay-panel attempt, because this content
  is deliberately compact (name + one-line description + chip labels,
  no full explanation paragraphs) rather than the full detail text.
  "More details ↓" scrolls to the full panel, which gets the same
  light-card/accent-stripe treatment and sits below the walkthrough —
  both panels now read as one system, per Ray's instruction. Muted text
  on the light cards was contrast-checked (not just eyeballed): default
  empty-state gray landed on `#5F5E58` (~6.5:1 on white) and the "More
  details" link on `#2563EB` (~5.2:1) specifically because the more
  obvious choices (`#6B7280`, the existing `#378ADD` link blue) computed
  under or barely at the 4.5:1 AA floor for normal-size text.

  **Layout**: hero → toggle → poster (with compact card) → walkthrough →
  full detail panel → case card → explanation text → footer, via a flex
  `.stack` with `order` values so mobile can reorder to poster →
  accordion → walkthrough → (panel hidden) → case card without
  duplicating markup. Explorer tab hides the shared full-detail panel
  (it already has its own inline side-panel) — a design call Ray
  confirmed rather than an assumption.

  **Combined hero**: single hero (family gradient + laser, unchanged
  shape) replacing the old two-block header. New "ECOSYSTEM MAP" badge
  and a teal accent (`#2DD4BF`) on the badge, laser highlight, and
  tagline gradient only — confirmed scope, not extended elsewhere on the
  page, so the established parent-matched glow language on buttons/
  hotspots stays consistent with the rest of the family.

  **E-items, all six built**: deep links (`#stakeholder-id`, updates via
  `history.replaceState` on selection — found and fixed a real bug here
  too: the initial hash must be captured *before* `showStep(-1)`'s
  internal `updateHash()` call overwrites it, or the deep link silently
  no-ops); glossary tooltips (dotted-underline spans in the explanation
  card, content pulled from `GLOSSARY` at render time so definitions
  can't drift from a second copy); a second "Follow the money" walkthrough
  (mode toggle inside the walkthrough bar, business-relationship framing
  only, no tax framing per instruction, drafted from and cross-checked
  against existing `RELATIONSHIPS` — no new facts introduced); a
  "Download poster" button (plain `download` attribute on the existing
  full-res image, no new asset); a "Content reviewed: September 2026"
  note driven by `CONTENT_REVIEWED` (see reminder below); Left/Right
  arrow keys step the active walkthrough, with the existing 90ms fade
  applied to the walkthrough text too.

  **Content-review reminder**: the Fortum/Microsoft case study describes
  a project whose waste-heat recovery phases in from 2027 — re-check
  `CASE_STUDY` and the explanation card's waste-heat paragraph against
  Fortum's public reporting periodically (at least whenever
  `CONTENT_REVIEWED` is bumped), since "today" language in that text
  will go stale as the project progresses.

  **Verified with a real headless browser (Playwright/Chromium)** at
  1850px/1280px/375px: before/after screenshots against the live
  pre-Phase-D page (confirms the panel-ghosting fix and lighter chrome
  side by side — the poster's own night-photo mood is unchanged, that's
  the source image, not a bug); light-card screenshots for the default,
  single-selected, and combined TSO/DSO states at both desktop widths;
  a walkthrough step and the case-card highlight both showing the fixed
  "Currently highlighted" panel state; the money-walkthrough toggle and
  its own highlight set; keyboard Left/Right stepping; glossary tooltip
  content sourced correctly from `GLOSSARY`; the download button's
  `download` attribute; deep-link preselection (caught and fixed the
  hash-ordering bug above during this pass); and mobile's toggle/
  compact-card hidden, accordion visible. Zero JS console errors across
  every viewport and interaction tested.

- **`ecosystem.html` — dark-glass panel redesign, layout, and first-render
  fixes (Phase E, 2026-09-22).** Data file bumped to `ecosystem-data.v4.js`
  (equipment stakeholder's description corrected — it listed cooling/
  storage/networking/backup power as its own items while those already
  have dedicated stakeholder nodes, contradicting the poster's own box).

  **Panel restyle**: the light frosted-glass card from Phase D was
  restyled to match the poster's own illustrated "Selected stakeholder"
  panel (measured directly from `Output/Datacenter environment.webp`,
  not memory) — dark navy glass, neon border/glow in the selected
  stakeholder's own sampled accent color, a round icon ring (14 hand-
  authored stroke icons), "Typical relationships" / "Typical value flows"
  sections (the latter as colored arrows matching the flow-type legend),
  and a "More details →" button styled after the illustration's "View
  details." Applied identically to the full panel below the walkthrough
  and to the "How a data center actually works" explanation card, so all
  three read as one system. Contrast re-verified for light-on-dark (the
  inverse risk from Phase D's dark-on-light) — worst case is a *bright*
  patch of poster behind the card; at 0.82 base opacity, dark navy over
  white still composites to ~11:1 contrast for white text.

  **Column-fill mechanics, tuned twice**: the compact card was first
  built with `max-height` (a ceiling, so short content left a large gap
  below the card) — changed to a **pixel-measured fixed height**
  (`panelBackdrop.getBoundingClientRect().height`, not a CSS percentage
  chain, which didn't reliably resolve through `.panel-backdrop`'s own
  percentage height against `.poster-frame`'s auto height) so the card
  always fills the column regardless of content length. For content that
  still overflows the fixed height (e.g. combined TSO/DSO), the "All
  stakeholders" list collapses to a single `<details>` toggle row once a
  stakeholder is selected — expanded only in the true default state —
  freeing most of the column; a bottom-edge fade plus a styled (not
  browser-default-invisible) scrollbar make remaining overflow obvious.
  List row spacing and icon size (22px, brightened via a `brighten()`
  helper for legibility — the *true* sampled accent stays unchanged for
  borders/glows) were tuned so all 14 entries fit without scrolling in
  the default state at 1850px; 1280px scrolls, which is accepted.

  **Layout**: the walkthrough (both paths, Prev/Next, step text) moved to
  sit directly between the view toggle and the poster/explorer, so its
  highlights land in the same viewport as the poster at wide widths
  instead of being scrolled off below a full-height poster image. The
  full panel below no longer duplicates the "Currently highlighted"
  summary the compact card already shows next to the glowing boxes.
  "Show highlighted" on the case card (which still sits below the fold)
  scrolls the poster/explorer into view.

  **Two first-render bugs, one root cause, now one fix point**: a hand-
  rolled opacity+`setTimeout(…, 90)` fade pattern, used both for the
  compact card's content swap and for the walkthrough's intro text, left
  each at `opacity:0` on a cold first paint (confirmed via a Playwright
  timing trace: two overlapping fade timers racing during init). Fixing
  the card's instance didn't prevent the same pattern from being
  hand-rolled again for the walkthrough text days later — so both were
  replaced with a single `safeFade(el, apply)` helper that every fading
  update on this page now routes through, skipping the timer entirely on
  the very first paint. New fades added in the future can't reintroduce
  this bug by forgetting a guard, because there's no longer a second
  place to forget it. **General lesson**: a hand-rolled async-UI-timing
  pattern (fade, debounce, delayed reveal) that gets copy-pasted instead
  of centralized will reproduce its bugs at each copy — centralize the
  first time a second copy is about to be written, not after a third bug
  report.

  **Verified with Playwright** at 1850px/1280px/375px across every round
  of this phase: hotspot/list-click selection, the collapsed-list state
  under long combined content (confirmed complete text via scroll-to-
  bottom, not just "doesn't visibly clip"), fixed-height column-fill in
  both long- and short-content states (gap consistently ~10px, matching
  intended padding, vs. up to ~280px before), walkthrough-above-poster
  glow visibility without scrolling, case-card scroll-into-view, the
  centralized fade fix (3 fresh-load trials, opacity:1 and correct text
  immediately, both card and walkthrough), and a full click-through
  regression (select → walkthrough → case card → view toggle) at all
  three widths. Zero JS console errors throughout.

- **`ecosystem.html` — COMPLETE (2026-09-22).** Ray reviewed the live
  page after Phase E and considers it done. Final feature set: poster-
  primary interactive view (measured hotspots, dark-glass compact card,
  clickable "All stakeholders" list), a secondary "Relationship explorer"
  SVG tab, two guided walkthroughs ("Life of a data center" and "Follow
  the money") positioned above the poster, a case card (Fortum ×
  Microsoft) with scroll-into-view, glossary tooltips, URL deep links
  (`#stakeholder-id`), a dark-glass explanation section, and a mobile
  fallback (static poster + accordion). No further changes planned
  unless Ray reports something from his phone or from the deep-link
  check specifically.

  Two small backlog items, not urgent:
  1. **Case card text width** — its paragraph runs the full card width
     (~250 characters/line on wide screens) while the explanation
     section below it constrains to `max-width:760px`. Should match.
  2. **Compact card occasionally falls short of its backdrop column** at
     certain window sizes or zoom levels. The card's height is measured
     in pixels from `.panel-backdrop`'s rendered `getBoundingClientRect()`
     at render time (see Phase E above) but is only recalculated on the
     `resize` event — browser zoom doesn't reliably fire `resize` in
     every engine, so a zoom change after page load can leave the cached
     height stale. Likely fix: also listen for zoom-affecting signals
     (e.g. `visualViewport.resize` where available) or recompute on a
     broader trigger — not yet investigated in depth.
  3. **Glossary tooltip runs off-screen on phones. Confirmed on the live
     site, 2026-10-06.** At 360px, tapping "colocation" opens a tooltip
     spanning x=179–409 on a 360px screen, giving the whole page 49px of
     sideways scroll. Cause: `.gloss-tip` is a fixed 230px wide, anchored
     at the term's left edge, with no viewport clamping. Fix in the round
     where this page switches to `business-models/assets/glossary.js`
     (build-order step 8), which keeps every tooltip inside the screen. Not
     fixed separately in the meantime.

- **`render.py` — swipeable sub-layer cards on mobile (2026-09-22).** The
  5-card `#chain` row didn't fit 375px screens — `min-width:120px` per
  card forced `body.scrollWidth` to 705px, dragging the whole page into
  horizontal overflow (confirmed the hero's compact sub-layer status
  strip and the ticker band were never independently overflowing; they
  were just collateral damage from `#chain`'s overflow). Fixed with a
  standard horizontal scroll-snap row, mobile-only: `overflow-x:auto` +
  `scroll-snap-type:x mandatory` on `#chain`, `scroll-snap-align:start`
  per `.layer` card, cards at `flex:0 0 80vw` so the next card peeks in
  as the swipe cue, a right-edge fade (`#chain-fade`, JS-toggled on
  scroll/resize) that hides once scrolled to the end, and `.chain-arrow`
  connectors hidden below 768px since they don't fit at 80vw card width.
  Desktop untouched (all new CSS scoped inside the existing
  `@media(max-width:768px)` block). Dots were considered and dropped —
  5 cards plus the peek+fade cue was judged clear enough without the
  added scroll-position-tracking complexity.

  **Root cause of two sub-bugs while building this, both the same
  pattern**: `buildChain()` was setting layout properties (`flex`,
  `min-width` on cards; `display` on the arrow connectors) as **inline
  styles** via `el.style.cssText`, which always wins over any external
  CSS rule regardless of specificity — so the new mobile media-query
  overrides were silently losing to values JS had already set inline.
  Fixed by moving the static layout values into proper CSS rules (the
  base `.layer` rule, a new `.chain-arrow` rule) and leaving only the
  genuinely per-score dynamic values (`background`, `border-color`, the
  conditional selected-state `box-shadow`) inline. **General lesson**:
  in this codebase, layout properties assigned via inline styles in JS
  are invisible to CSS media queries and will silently block them —
  static/structural layout values belong in CSS rules; only values that
  must be computed per data point (a color from a score, a computed
  glow) belong inline.

  **Verified** against a real pipeline run (`python main.py --now`, live
  data — this is a template/CSS change, not a scoring change, but the
  embedded `LAYERS` JS data still needs to come from a real run to test
  against) with Playwright at 375px/414px/1400px: `body.scrollWidth`
  matches the viewport exactly at both mobile widths (was 705px
  overflowing a 375px viewport before the fix), card width resolves to
  exact 80vw, fade shows/hides correctly at scroll start/end, the expand
  panel still opens below the row on tap, and desktop card width is
  pixel-identical before and after (249.1875px). Zero console errors.

- **`ecosystem.html` — compact-card collapse bug fixed (root-caused, not
  patched around) + body text brightened (2026-09-22).** Ray reported the
  compact card intermittently rendering as a thin strip (title only,
  description cut off mid-sentence) for some stakeholders but not others
  in the same session — plus the standing backlog item that the card
  sometimes ended short of its frosted column.

  **Reproduced deliberately before any fix was written**: routed the
  poster image request through a 1.5s artificial delay (Playwright
  `page.route`) and loaded `ecosystem.html#equipment` (a deep link
  auto-selects on load, the same as a fast click right after page load).
  Sampled `#compact-card`'s height every 300ms through the load. Result:
  at t=743ms the image hadn't loaded (`img.complete === false`,
  `naturalHeight === 0`), `#panel-backdrop`'s rendered height was only
  20px (its own padding — `.poster-frame` has no height yet, since
  nothing else in normal flow gives it one before the image paints), and
  `#compact-card`'s height got locked to the 60px floor at that instant.
  At t=1987ms the image finished loading and the backdrop correctly grew
  to 625.6px — but the card's height **stayed at 60px for the rest of
  the 3.5s observation window**. Root cause: `syncCompactCardMaxHeight()`
  was only ever called from `updateLightCards()` (on selection change)
  and on window `resize` — neither fires when the image finishes loading
  after the initial synchronous script run, which is exactly what
  happens on an uncached hard reload or a deep link that auto-selects
  before the image has painted. Once locked in, nothing re-measured it,
  because a click on a *different* stakeholder re-measures fine (image
  is loaded by then) — which is why it looked stakeholder-specific and
  intermittent rather than a clean, obvious, always-reproducing bug.

  **Fixed the root cause, not the symptom**: added a `ResizeObserver` on
  `#panel-backdrop` itself, so any future change to its rendered size —
  image load, orientation change, zoom, a reflow from something above it
  — triggers a re-measurement automatically, without needing every
  possible trigger enumerated by hand (which is exactly how this bug was
  introduced: `resize` was wired up, image `load` wasn't). Kept an
  explicit `poster-img` `load` listener alongside it (redundant with the
  observer once the image loads, but a fast, obvious first re-sync
  rather than depending solely on the observer's own scheduling) with an
  `img.complete` check for the already-cached case. This ResizeObserver
  fix is also the fix for the "card ends short of the column" backlog
  item — same stale-measurement root cause, just a smaller gap most of
  the time rather than a full collapse. **Also added the requested
  safety net regardless of cause**: the height floor went from 60px
  (visibly a broken sliver) to 200px (`COMPACT_CARD_MIN_H` — enough for
  the icon row + name + a couple of lines), so even a future, unforeseen
  measurement failure can't render as a collapsed strip.

  **Verified**: re-ran the exact reproduction with the fix in place —
  card now correctly reaches 605.6px once the delayed image loads,
  instead of staying at 60px. 8 consecutive hard reloads at normal speed
  (no artificial delay): all 8 landed at 605.6px, backdrop 625.6px, a
  consistent 20px gap (the backdrop's own padding — not a bug) instead
  of the variable/large gap reported before. Checked 4 viewport heights
  (700/900/1100/1400px at fixed width): identical result at all four,
  since the poster's rendered size is width-driven, not height-driven,
  ruling out a height-dependent race too.

  **Body text brightened** (separate from the collapse fix, same round):
  stakeholder descriptions (`.sc-subtitle`), relationship explanations
  (`.sc-rel-list li`), value-flow labels (`.sc-flow`), the compact card's
  "How to use this map" body copy (`.sc-howto-list li`), walkthrough step
  text (`.wt-desc`), and the explanation section's paragraphs
  (`.explain p`) all moved from muted blue-gray (`#AEB9CC`/`#C8D2E4`) to
  near-white `#E8EDF5`. Left untouched, deliberately: section headings
  (`.sc-heading`/`.sc-heading-sm`, already `#fff` bold — hierarchy was
  already coming from weight, not dimming, exactly as intended), the
  "Content reviewed" note, source lines, and the "All stakeholders" list
  item labels (kept at the dimmer tone specifically so the `#fff`
  active-item state still reads as a distinct highlight, not requested
  to change and would have removed a working signal). The case card's
  body text (`.case-body`) wasn't in Ray's original four named regions
  but was brightened too on review — same reading content on the same
  page, no principled reason to leave it dimmer.

  **Contrast re-checked, not assumed improved**: worst case is a bright
  (white) patch of poster behind the glass, composited with the card's
  0.82-opacity dark-navy base to roughly rgb(54,59,71) — the same
  worst-case background used for the dark-glass panel contrast check.
  `#E8EDF5` against that computes to ~9.5:1, clearing AA's 4.5:1 with
  a large margin and exceeding AAA's 7:1 for normal text too.

  **General lesson, reusable beyond this one bug**: when a layout
  dimension is measured in JS rather than left to CSS, watch the
  measured element with `ResizeObserver` rather than re-triggering the
  measurement from a hand-picked list of events (`resize`, `load`, a
  click handler, …). An enumerated trigger list is a claim that every
  way the element's size can change has been anticipated — this bug
  existed because that claim was wrong (image `load` wasn't wired up,
  only `resize` was), and the next missed trigger (a font swap, an
  orientation change, a dynamically inserted sibling) would reproduce
  the same class of bug through a different door. `ResizeObserver`
  reports the actual current size whenever it changes, for any reason,
  which removes the category of bug instead of patching one instance of
  it. This applies equally to the parent `AI_valuechain` repo's own code
  if it measures any element's layout in JS — worth checking there too,
  not just here.

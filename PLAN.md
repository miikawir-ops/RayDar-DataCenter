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

   **Persisted since 2026-10-15 (ledger R33a/c, R59).** Each run restores
   `scores_history.json` and `audit_log.json` from the `data` branch and a
   separate save job commits them back. The audit log keeps one entry per
   ticker per session with the accel/constraints/smart sub-scores,
   fund_delta and model_version, with no cap: that is the per-ticker
   history this question needs. The first stored session is Wed Oct 14
   (run 38795478655). Both files started empty; nothing was seeded from
   the recovered logs.

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
     **Why Finland raised to 10/2026 (2026-10-22, ledger R74)** after a full pass of
     all its facts; the other pages' labels stay 9/2026.
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
| R16 | 2026-10-08 | "Review date: this is the first genuine fact update since the 'tiedot tarkistettu 9/2026' label was introduced. Don't bump the label globally. Propose to Ray which pages you've actually re-verified, so the date is raised only there." | **done** (audited 2026-10-21, R67): `5ab7fc8` and `3604863` are on main; the live public-cloud.html and value-chain.html fine print say "tarkistettu 10/2026", page labels still 9/2026. Open for Ray (the rule, not this row): later single-fact updates didn't get "tarkistettu 10/2026" in their page's fine print: retail-colocation.html (R54 electricity item, R64 network-ecosystem figures), own-data-center.html (R56 electricity wording) and the hub (R54 matrix rows; R61/R62 waste-heat and R64 Z5 panels carry their own source lines but no date). Before the audit: **accepted** (Ray: "Keep the 9/2026 labels; date the updated facts themselves with 'tarkistettu 10/2026' in the fine print of the pages you actually changed. Don't raise any page label without a full pass of that page's facts."); **done:** "tarkistettu 10/2026" in card 1's and the value chain's fine print (`5ab7fc8`, `3604863`), live 2026-10-08; rule recorded in step 8 under the review-date label |
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
| R29 | 2026-10-09 | PART B, ecosystem page: "1. In money step 1 a € badge covers the poster's 'Lease & services (compute capacity)' label. Place badges so they never cover printed poster labels; add a check for overlap with label boxes if practical. 2. The explorer has no operator ↔ enterprise relationship, although the poster draws one and money step 1 charges 'Enterprise → Operator: colocation fees'. Recommend whether to add it (e.g. operator → enterprise, colocation space, power and cooling), with type and wording. Show me the wording before committing; it's new user-facing text. 3. On a fresh load, check that clicking the already-active 'Life of a data center' chip starts step 1. If it doesn't, fix it and add the case to check_ecosystem.py." "Run the four checks, verify live after deploy, quote hashes only from command output." | **done** (audited 2026-10-21, R67): B1 `ac197b2`, B3 and the overlap check `b49c2ce`, B2 via R31 `b1f3b34`, all on main; live ecosystem-data.v9.js has the operator -> enterprise colocation relationship; check_ecosystem.py 193/193 against the live site (2026-10-21). Before the audit: **B1/B3 done** (`ac197b2`, `b49c2ce`, live 2026-10-10); **B2 approved** with an extended explanation, see R31 |
| R30 | 2026-10-10 | "1. Disclosure (ship first, on its own). Render the note _confirmed_color() already returns on each sub-layer card, so the disclosure stays correct by itself once persistence is live. While any sub-layer is unconfirmed, add one page-level line, e.g. 'Colours currently reflect a single day's reading; multi-day confirmation isn't active yet.' Show me the exact page line and every note variant before committing." | **done** with R36's changes: `e047238`, live 2026-10-10 (all five cards show the insufficient-history note, plus the page line); wording superseded in part by R42 (session, not 'today') |
| R31 | 2026-10-10 | "2. R29: approved, with this explanation (label unchanged): 'Businesses rent space in the operator's facility for their own servers, usually racks or a cage in a shared hall (retail colocation), with power and cooling supplied by the operator and often direct connections to carriers and cloud providers in the same building.'" | **done:** `b1f3b34`, live 2026-10-10 (ecosystem check 103/103 against the live site) |
| R32 | 2026-10-10 | "3. Read-only snapshot before building persistence: a. Run the pipeline locally once (weekend, so Friday's full bars) and give me per ticker: accel, constraints, smart, composite, fund_delta, and whether accel×0.65 + smart×0.15 ≥ 45. b. For the 15 recovered days: which run per day you used, and for days with several runs, the spread of each sub-layer's score within the day." | **done:** reported 2026-10-10 (local run on Friday's full bars; per-ticker table; per-day runs and within-day spreads) |
| R33 | 2026-10-10 | "4. R28 persistence: data branch approved, with these changes: a. Split the workflow: build/deploy keeps contents: read; a separate small job with contents: write receives only the two files (as an artifact) and pushes them to the data branch. b. Instead of 'weekday scheduled runs only': date each history and audit entry by the last completed US market session, not the wall clock; the last run for a session overwrites earlier ones. First verify, on a run during US trading hours, whether t.history(period='6mo') includes today's unfinished bar. If it does, drop it: vol_spike = volumes[-1]/vol_avg otherwise depends on when GitHub fires the cron. Report how many of the 15 recovered days came from intraday runs. c. Audit log on the data branch: one entry per ticker per session, no 500-entry cap, including accel/constraints/smart and fund_delta. This is the data the Red-threshold question needs. d. Missing-day fix as you proposed: excluded and named, never 0; days older than 7 calendar days excluded; an unreadable file in CI is an error. e. Commit the 15 rebuilt days and the raw run logs to the data branch under archive/, never read by the pipeline, before the logs expire. f. Confirm that a failed scheduled run actually notifies me. g. Activating confirmation: approved, with the before/after check on live per CLAUDE.md. Report the notes from the first live runs." | **done** (audited 2026-10-21, R67): a `238e4dd`, c `b924eb9`, tests `48717dc`; b and d `4d9eeb1`, tests `03b7466`; e: origin/data has archive/ (README, rebuilt 2026-09-20..10-09 history, run_logs); f via R38/R39 (`ceb1e22`, `e50568a`); g active since the third stored session. Checked 2026-10-21: deploy.yml gives contents: write to save-history only and has report-failure; origin/data holds 5 sessions (2026-10-14..10-20) and 60 audit rows (12 tickers x 5), all model_version 2. Runs that never start remain a tracked known issue, not open R33 work. Before the audit: **a, c, g done** (R59): `b924eb9` (audit log, one entry per ticker per session, no cap), `238e4dd` (workflow: restore from the data branch, save-history the only job with write access), tests `48717dc`; data branch started empty `807a7c9`; first persisted run 38795478655 (2026-10-15, session Oct 14), confirmation active from the third stored session (Mon 2026-10-19's run). **b verified** (R59): every trading-hours run dropped the unfinished bar. Earlier status: e done (data branch `1bc7b92`, archive/); **f closed** (R39): GitHub's "Run failed" email arrived for the 10:23 UTC test run (38044696377), so failure emails reach Ray; the failure issue job (`ceb1e22`) runs as well. Known gap: a run whose job never gets a runner (2026-10-05) sends neither (Known issues, "Runs that never start"); b: 13 of 15 recovered days were intraday runs; **b and d live** since 2026-10-10 (`4d9eeb1`, tests `03b7466`; manual run 38068453210); Monday 2026-10-12's scheduled run is the R33b check only (R58) (before: `Output/before_after_r42/`); Monday's log also shows whether yfinance returned an unfinished bar (each dropped bar is logged); a, c, g to build. d's tests must include a weekday session with no entry because its run never started (the 2026-10-05 case): excluded, named in the note, never 0 (R39) |
| R34 | 2026-10-10 | "5. PLAN.md, doc only: a. Add a lesson: the parent's commit-back step both published index.html and persisted history; the Actions-based deploy replaced the first and dropped the second. Before replacing a parent mechanism, list everything it did. b. Add to the open queue, to carry over to the parent's own session (don't change AI_valuechain from here): its _load_recent_layer_scores has the same .get('score', 0), and there the history persists, so the bug is live. Its 06:00 UTC run dates yesterday's session as today, and its 20:30 UTC run falls before the US close after 1 Nov (close is 21:00 UTC in winter), so the session-dating fix applies there too." Plus: "Run the four checks, verify live after each deploy, quote hashes only from command output." | **done:** `b5bc8b5` |
| R36 | 2026-10-10 | R30 changes: "1. Show the page line only while at least one card is in the insufficient-history branch, not 'while any sub-layer is unconfirmed'. After persistence goes live, 'not sustained' cards must not trigger it. Wording: 'Colours are based on today's reading only; multi-day confirmation starts once a few days of history are stored.' 2. Make the notes plain, once, inside _confirmed_color() (so the page follows the data). Proposed wording; adjust only where it would be inaccurate: insufficient history: 'Today's reading only — not yet confirmed (N of 2 earlier days stored)'; instant Red, score: 'Red without waiting: score {x} is above 80'; instant Red, delta: 'Red without waiting: the leading company's revenue growth is accelerating sharply'; confirmed: '{Colour}, confirmed: {n} of the last 3 days also {above/below} {t}'; holding: 'Kept {Colour}: today's score {x} is near the line, and recent days were mostly {Colour}'; not sustained: 'Shown as {displayed colour}: today's {x} hasn't held over recent days'. Show me the final strings and screenshots, then commit, deploy and verify live. R31 follows as planned." R33: "3. Build session dating defensively now: drop any bar dated today in US/Eastern unless the session has closed, and date entries by the last completed session. Monday's trading-hours run then verifies it; it doesn't decide it. 4. Add a final workflow step that opens a GitHub issue when the run fails (on top of email, which I'll confirm separately)." | **done** (audited 2026-10-21, R67): 1-2 `e047238`; 3 `4d9eeb1` (live since manual run 38068453210 on 2026-10-10, not first at Monday's run as noted below); 4 `ceb1e22`. Live 2026-10-21: no single-session page line (history stored), notes use the confirmation wording. Before the audit: **1–2 done:** `e047238`, live 2026-10-10. **4 done:** `ceb1e22` (see R38). **3 committed** `4d9eeb1` with R42's decision (prices, the day's move and VIX from completed-session bars), live at Monday 2026-10-12's scheduled run, which is the before/after check (before: `Output/before_after_r42/`). Note wording superseded in part by R42 |
| R35 | 2026-10-10 | "R35, new, read-only, before any weight change: 5. The R32 snapshot suggests the 65/20/15 weights cap the constraint signal at 20 points, so optical (constraints 70–100) can't get past ~52. Before proposing anything, check the inputs: a. Constraints: for COHR (100.0), LITE (90.1) and CIEN (87.7), list the headlines and keyword matches behind the score. Is 100.0 a cap being hit? Does keyword purity hold (no bare names or tickers)? Are headlines layer-filtered? b. Smart money: why it is 0.4–19.6 for all 12 tickers. Show each component per ticker (volume-price, analyst, short interest), which are None or missing, and how missing values are handled. If missing is scored as 0, that breaks decision #6: report it, don't fix it yet. c. Only once a and b are clean: show what composite and colour each sub-layer would get under 2–3 alternative weightings, against today's snapshot and the 15 recovered days. No proposal or change to the live weights; that needs my approval and a before/after check." "Quote hashes only from command output." | **a, b reported** 2026-10-10 (not clean; findings under Known issues, "Scoring inputs"). **c held** until a and b are clean |
| R37 | 2026-10-10 | "Amend the parent carry-over note in PLAN.md (item 5b of my last instruction), doc only, commit by path: Replace the point about the 20:30 UTC run falling before the US close after 1 Nov. The parent's bot commits show its crons fire 4–7 hours late (morning ~10:30–13:25 UTC, evening ~23:00–01:20 UTC). Consequences: the evening run sometimes lands after midnight UTC, so a date's entry holds either that day's or the previous day's session; a Friday evening run can write a Saturday entry (2026-10-10 00:08 UTC), counting Friday's session twice; the 2026-10-05 morning run committed at 13:25 UTC, minutes before the US open. Verify these from `git log --author=bot` in the parent before writing them down." | **done:** `58479cd`. Two points corrected on verification: the evening cron fires 2.2–4.8 h late, not 4–7 h; Friday 2026-10-09's session is in one entry so far (the Saturday one), since Friday's own entry holds Thursday's. The double counting comes from Monday-morning entries (2026-09-28, 2026-10-05) |
| R38 | 2026-10-10 | "R33.f: I received no email for the 2026-10-05 run. Treat the report-failure issue job as required. When you run its deliberate test failure, tell me the time so I can check whether an email arrived too." | **done:** `ceb1e22` (job `report-failure`, plus a manual-only `test_failure` input). Tested 2026-10-10: run 38044696377 failed on purpose at 10:23:05 UTC, and issue #1 opened at 10:23:09 UTC, assigned to miikawir-ops (closed afterwards as a test). Normal run 38044762500 skipped the job and deployed, live 10:24 UTC. Tested on main, not a throwaway branch: the github-pages environment only allows main. GitHub's "Run failed" email for that run arrived (Ray, R39) |
| R39 | 2026-10-10 | "R33f: I received GitHub's 'Run failed' email for the 10:23 UTC test (Deploy RayDar Data Center dashboard, main, ceb1e22). Failure emails reach me. Close R33f with that recorded. Record as a known gap: the 2026-10-05 run was marked failed but its job never started, and I got no email for it. Check whether report-failure (if: failure()) would fire in that case; if not, say so in PLAN.md. The detection for that case is R33d's missing-day note, so include it in R33d's tests as already asked." | **done:** `e50568a`. `report-failure` wouldn't fire: the job's result was `cancelled`, not `failure`, and the job never got a runner, which the report job also needs |
| R40 | 2026-10-10 | "R33d: expected sessions from trading dates approved. Take them from a reference series every run fetches (e.g. ^GSPC daily bars); if that fetch fails, the run fails loudly, never 'no sessions expected'. R33d addition: include a test where a scheduled session is missing entirely (e.g. a run that never started, like 2026-10-05) and show that the card note names the missing day." | **done:** live since 2026-10-10 (manual run 38068453210, R43, which also did the before/after on the Fri Oct 9 close); R58 left Monday's run only the R33b check. Earlier status: committed `4d9eeb1` (tests `03b7466`) with R42's wording, live at Monday 2026-10-12's scheduled run, which is the before/after check (before: `Output/before_after_r42/`). Built 2026-10-10 and held for Ray's approval of the note wording ("(no reading for Mon Oct 5)"). `tools/check_confirmation.py` 28/28, including the 2026-10-05 case end to end through stage_score() and the rendered card. Open with it: the card's "vs yesterday" delta compares against the latest stored session, so with Mon Oct 5 missing it compares Tue Oct 6 with Fri Oct 2 under the same label |
| R41 | 2026-10-10 | "R33.3 addition: the bar helper must also drop any trailing row whose Close is NaN, regardless of its date, and any NaN that still reaches a computed value must become None and be named in data_missing (decision #6), never written to the page. Evidence: the parent's published page has "ret30": NaN for all 28 tickers on almost every run after 00:00 UTC (e.g. 10-10 00:08, 10-09 00:32, 10-08 00:17) and on none before midnight; likely an empty last bar. Add a test with a trailing NaN row. Also add this to the parent carry-over queue." | **done:** live since 2026-10-10 (manual run 38068453210, R43, which also did the before/after on the Fri Oct 9 close); R58 left Monday's run only the R33b check. Earlier status: committed `4d9eeb1` (tests `03b7466`), live at Monday 2026-10-12's scheduled run, which is the before/after check (before: `Output/before_after_r42/`). `tools/check_confirmation.py` 41/41, including a trailing NaN row dated a past session (fails on the previous helper). Found on the way: before the clamp check, a NaN close made momentum +5, the maximum. Carry-over entry added; one correction to the evidence: one morning run (2026-09-23 10:40 UTC) also has NaN |
| R42 | 2026-10-10 | "R40 and R41 approved with these changes. Log them in the ledger with my words. 1. Wording: scores now belong to the last completed session, not 'today'. Page line: 'Colours are based on the latest session's reading only; multi-day confirmation starts once a few sessions of history are stored.' No history: 'Latest session only — not yet confirmed (1 of 2 earlier sessions stored; no reading for Mon Oct 5)' Confirmed: 'Orange, confirmed: 2 of 2 available recent sessions also at or above 40 (no reading for Mon Oct 5)'. Use 'N of M available recent sessions' whenever a session is missing, and 'N of the last 3 sessions' otherwise. Holding and not sustained: as proposed, but 'latest score' instead of 'today's'. Several missing: as proposed. 2. Score delta: always label it with the comparison session's date ('vs Fri Oct 9'), never 'vs yesterday'. 'Yesterday' is wrong on every Monday and after holidays, not only after a missing session. 3. Data date: next to 'Fetched…', show the session the scores belong to, e.g. 'Data: close of Fri Oct 9 · fetched 18:24 UTC'. 4. R36 item 3 decision: price, the day's price move and VIX come from the kept completed-session bars like everything else; show the price with its session date. No live intraday quote anywhere in scoring or on the cards. Show me the final note strings and one screenshot, then commit R40/R41 code and the test tool separately and push. Monday's scheduled run is the before/after check on live; report it." | **done:** live since 2026-10-10 (manual run 38068453210, R43, which also did the before/after on the Fri Oct 9 close); R58 left Monday's run only the R33b check. Earlier status: committed `4d9eeb1` (code), `03b7466` (tests, 57/57); strings and screenshot shown 2026-10-10. Accuracy adjustment: "N of M available recent sessions" is also used when fewer than 3 sessions are stored without a gap (the first days of a history), so a note never implies a session was checked that wasn't. Market cap is Yahoo's rescaled to the session close (shares x close is wrong for DELL: one share class). live at Monday 2026-10-12's scheduled run, which is the before/after check (before: `Output/before_after_r42/`) |
| R43 | 2026-10-10 | "1. Wording: use 'recent sessions' instead of 'recent days' in the holding and not-sustained notes, for consistency. 2. Fix both minor items now: the header shows 'UTC' with its time, and the sparkline date labels count back from the session date, not the viewer's date. Update check_confirmation.py. 3. Commit by path and push, then trigger a manual workflow_dispatch run now (not test_failure). It scores Friday's close, the same session as the saved 'before' from Saturday 10:24 UTC, so compare the two: price-based inputs should be identical, and separate any score change into news vs code. Verify live (root, ecosystem, business-models hub), check the page text for NaN, and report. 4. Monday's scheduled run remains the trading-hours check (R33b): report whether an unfinished bar was dropped. Log in the ledger; quote hashes only from command output." | **done** (audited 2026-10-21, R67): `1824399`, `d91ff1a` on main; live 2026-10-21: header time in UTC, no 'recent days' or 'vs yesterday', no NaN in the visible text; item 4 done (R59). Before the audit: **1-3 done:** `1824399` (code), `d91ff1a` (tests, 62/62); manual run 38068453210, live 2026-10-10 16:38 UTC (root, ecosystem, business-models hub 200; no NaN, no 'vs yesterday', no "today's" in the page text). Sparkline labels are each point's own session date (sampled back from the session's bar) rather than counted back from it, so they can't drift. Before/after on the Fri Oct 9 close: price-based page fields identical except SMCI price 41.85 -> 41.86 (live quote -> official close) and 52-week highs rounded (VRT 379.935 -> 379.93, ANET 217.4099 -> 217.41). Networking 38.3 -> 39.5 is news (5.0 -> 6.0 hits). Code effect: zero, old (`ceb1e22`) vs new code on the same inputs and news, in both the local and CI's package versions (within 0.0001). Optical 43.6 -> 43.7: not news (10.0 both) and not code; the run's own inputs put it at least 0.01 higher, which crossed the rounding line; per-ticker inputs aren't kept in CI, so the input can't be named (R33c will keep them). Found on the way: CI installs yfinance 1.7.0, not the local 1.4.0 (Known issues). **4 done** (R59): the Mon 2026-10-12 run started after the close (nothing to drop); the Tue-Thu runs dropped that day's unfinished bar for every series |
| R44 | 2026-10-10 | "Pinning approved; do it first, before Monday's run, as its own commit: Pin every dependency in requirements.txt to the exact versions CI installed in run 38068453210 (yfinance 1.7.0, pandas 3.0.6, and the rest). Pin to CI's versions, not your local ones. Update your local environment to the same pins and re-run the four checks and check_confirmation.py on it. Add a check to the pipeline that fails loudly if an expected column or field is missing from yfinance data (e.g. the analyst source), so a future version change can't silently return 0 again. Log in the ledger, commit by path, push. No deploy needed; Monday's scheduled run picks it up." | **done:** `356ea61` (requirements.txt: all 25 packages CI installed, exact versions), `7976ff9` (.venv ignored), `e9e3fc8` (data-format check), `399d305` (tests). Local environment: a project `.venv` with the same 25 pins (plus Playwright and tzdata for the checks and Windows time zones); only Python differs (3.14 locally, 3.12 in CI; 3.12 isn't installed here). On it: check_confirmation.py 71/71, and the four checks pass. One deviation, to be confirmed by Ray: the analyst column is already missing, so a strict check would fail every run until R45 ships; it's logged as an error on every run instead (KNOWN_FORMAT_BREAKS), and nothing else may be added there. Live with Monday's scheduled run |
| R45 | 2026-10-10 | Row A, "input correctness (scoring change: replay first, then my approval, then a live before/after): 1. Analyst: score as missing (None, named in data_missing) when the expected data isn't there; read per-action grades from upgrades_downgrades if that's the correct source in yfinance 1.7.0. 2. Momentum: fix the sign when both returns are negative, the near-zero 90-day case, and the 5-day window. 3. News: count each story once across feeds; a ticker-feed headline counts only if it names that company; remove the bare-brand +1 for generic headlines (CLAUDE.md topical rule); generic headlines count for a sub-layer only through terms specific to that sub-layer, not the shared supply keywords. 4. Every history and audit entry carries a model_version, bumped whenever scoring inputs, formulas or weights change. Replay each fix separately on the 2026-10-09 session, plus all together, on the pinned versions. Show per ticker: before, after, and which fix moved it. Ship them together as one release, not before Monday's R33b check is reported." | **done:** merged `401e7b8` (R58), live 2026-10-11, manual run 38142625033; before/after in R58. Earlier status: replayed, held for Ray's approval and Monday's R33b report. Local branch `r45-input-fixes` (not pushed): `d959d14` analyst, `af1fe38` + `c406302` momentum, `d43b7c4` news, `7f82449` model_version 2, `86ff1e1` tests (93/93; the new ones fail on the old code). Replay on the 2026-10-09 inputs frozen in `Output/r45_replay/` (Python 3.12.10, pinned packages; report.txt): no colour changes (all Green); sub-layers cooling -1.36, networking -0.17, optical +0.77, compute +0.08, colocation -2.51 |
| R46 | 2026-10-10 | Row B, "design questions (proposals only, no change): a. Capex/operating cash flow measures cash-flow strain, not supply constraint (COHR 8.1 because cash flow is small). Propose an alternative (e.g. capex growth year on year, or capex/revenue) and show its effect. b. Short interest: I'm inclined to score it as missing until it has a defined meaning. Check whether yfinance gives a prior-month figure, so a change could be used instead of a level. c. R35c (alternative weightings) runs after Row A is live." | **open** |
| R47 | 2026-10-10 | "Parent carry-over queue: add that AI_valuechain has the same momentum formula (fetch_market.py:311), the same 'To Grade' analyst check (:380) and an unpinned yfinance (>=0.2.40). Queue: run_rate is null for all 12 tickers (revenue_quarterly filled only on a fallback path). Quote hashes only from command output." | **done:** `04be423` (parent carry-over entry, verified at the parent's HEAD `170ab49`; new "Queue (this project)" section with the run-rate item) |
| R48 | 2026-10-10 | "1. Analyst exemption: confirmed, but make it expire. Tie it to R45: when the R45 analyst fix is in place, the exemption itself must cause the format check to fail until it is removed (or tie it to model_version). Add a test for that. 2. Python: install 3.12 to match CI (e.g. `winget install Python.Python.3.12`, or the python.org installer), recreate .venv with `py -3.12 -m venv .venv`, reinstall the pins, and re-run check_confirmation.py and the four checks on it. Tell me if winget needs my approval. 3. Start the R45 replay now on the pinned 3.12 environment. Report before shipping; shipping waits for Monday's R33b report. Log in the ledger; quote hashes only from command output." | **done** (audited 2026-10-21, R67): 1 `73c0f19`, tests `1a5ab51`; the exemption itself was removed when model_version 2 shipped (fetch_market.KNOWN_FORMAT_BREAKS = {}, config.MODEL_VERSION = 2); 2 done (.venv on 3.12.10); 3 done via R45, merged `401e7b8`. Before the audit: **1 done:** `73c0f19` (MODEL_VERSION = 1 in config.py; the analyst exemption expires at model_version 2 and fails the run once expired, or once its field is no longer read), tests `1a5ab51` (75/75). **2 done:** Python 3.12.10 installed with winget, per user, no admin approval needed (CI runs 3.12.15; winget's latest 3.12 is 3.12.10); .venv recreated with `py -3.12`, all 25 pins matched; check_confirmation.py 75/75 and the four checks pass on it. **3 in progress:** inputs for the 2026-10-09 session frozen in `Output/r45_replay/` (feeds as of 2026-10-10 20:15 UTC; Friday's headlines were never stored); **done:** replay reported 2026-10-10, see R45 |
| R49 | 2026-10-10 | "From now on, critical work only. Log any new findings to the PLAN.md queue instead of raising them with me, unless they are a live bug. Batch everything that needs my approval into one message. R45 approved with one change: analyst counts only actions within a recent window (30 days, or the original code's window if different); a failed fetch stays None and is named. Re-run that replay; no need to show me unless a colour changes. After Monday's run: if R33b is clean, merge R45 (model_version 2), deploy and verify live without waiting for me; report in one message. Then build persistence (R33a, c, g) and send me ONE approval message with the before/after. Everything else (R46, R23, queue items) stays parked." | **in progress:** analyst window done on the R45 branch: `6b354db` (30 days up to the session; the original code had no time window, only its 10-most-recent limit, kept inside the window), tests `b972410` (96/96). Replay with all fixes: no colour change. R45 shipped 2026-10-11, ahead of Monday (R58); Monday's run does only the R33b check. Persistence (R33a, c, g) shipped 2026-10-15 under R59 (approved there as already approved, so no separate approval message) |
| R50 | 2026-10-11 | "Ecosystem page: make the navigation more prominent, within spec A5a (glow fine, no continuous animation). Work on main, not on the r45-input-fixes branch, and touch only the ecosystem page files, so Monday's R45 merge stays clean. 1. Walkthrough chips → two large buttons with an icon and a one-line description: 'Life of a data center — from permits to waste heat, step by step' and 'Follow the money — who pays whom'. Active state filled; money uses the poster's capital yellow, matching the money arrows. Add a small static 'Start here' label. 2. Link cards: stronger border glow, coloured icon tile, a visible 'Open →' pill instead of the small arrow, hover lift, and an 'FI' tag on the Finnish explainer card. 3. Poster / Relationship explorer: larger tabs with a clear active state, visually heavier than the walkthrough buttons. Send me screenshots at 1680 and 360 for approval before committing. Keep check_ecosystem.py green; add checks for the new buttons. Log in the ledger." | **superseded by R51**: committed as `f16a6e6` page and `ea43bd0` checks, then reverted before going live (`93154f9`, `da30d71`, 2026-10-11) because Ray's R51 revisions arrived after the commit; the revised version replaces it |
| R51 | 2026-10-11 | "R50 revisions before commit. The hierarchy is upside down: the page title is weaker than the tabs. 1. Page header: make it the dark hero of spec A5a, matching the Daily signals page hero (title size, gradient tagline), so the title is the strongest element at the top. 2. Tabs (Poster / Relationship explorer): back to normal tab size (about 16–17px, semi-bold), with a clear active state (fill or underline). If the money button then outshines them, tone the money button down instead of enlarging the tabs. Update the check that tabs outweigh the walkthrough buttons accordingly. 3. Link cards, differentiated by destination: Daily signals: dark blue 'live data' style, a static 'LIVE' marker (no animation), and the line 'Updated every weekday'. Datakeskusten liiketoimintamallit: the explainer's light cream background (#F3F1EB) with navy text (#12222E), previewing its editorial look; no rust. Keep the FI tag and the Open pills. Make both cards more compact in height. 4. Walkthrough icons: don't reuse stakeholder icons. Money gets a € symbol, Life gets a timeline or crane symbol. 5. Vertical space: with the header, tabs and cards compacted, the top of the poster should be visible in the first screen at 1680×1050 and 1280×800. Report where it starts. 6. Check for clipping or horizontal scroll at the right edge at 1280, 1440, 1680 and 1920 ('Content reviewed: …', the Open pills and the Next button). Fix any. Send screenshots at 1680 and 360 again for approval before committing. Keep check_ecosystem.py green." Then: "Don't wait for my screenshot approval or Monday." | **done:** `e8cdd85` page, `b6c97d1` checks; manual run 38120160894, live 2026-10-11. Live: root, ecosystem.html and business-models/ 200, no NaN, no sideways scroll at 1280/1440/1680/1920 (dashboard and hub too); check_ecosystem.py 175/175 against the live site; poster starts at 411px at 1680x1050 and 1280x800 |
| R52 | 2026-10-11 | "Content round, goal: describe the ecosystem and business models in the most essential, comprehensive, understandable and professional way, for a wide audience (not only tax readers). New ledger row. All new user-facing text needs my approval, with sources, before committing. Do it in two parts. Part 1, ecosystem page: 1. Follow the money: a. Add a step 'The public sector's share', in general terms: land sale or lease and permit fees (→ municipality), property tax (→ municipality), electricity tax and income tax (→ state). Verify against official sources and state only what they support. b. Step 1: add that in a hyperscaler's own facility there is no rent; the hyperscaler builds and operates the site itself. c. In the step where the operator pays its suppliers, one line linking to the Daily signals page: this is the investment flow it tracks. 2. Examples: each stakeholder's detail card gets an 'Examples' line with 2–3 well-known global companies and 1–3 Finnish ones, each publicly verifiable, with sources and a review date. For the supplier and colocation boxes, take the listed companies from the dashboard config (not typed by hand) and link to that sub-layer's card. 3. GPU cloud (neocloud): propose adding it as its own stakeholder (box text, relationships, examples), since it's now a central model. Proposal only; show me before building. Part 2, business-models explainer (after part 1 is approved): 4. Check the five-model matrix covers what distinguishes the models: who owns the building, who owns the IT equipment, who pays for electricity, typical contract length, and who bears vacancy/utilisation risk. Propose additions for any gaps (Finnish text, registered in port_deviations as usual). Keep all checks green and extend check_ecosystem.py for the new step, examples and links." | **done** (audited 2026-10-21, R67): Part 1 via R53, Part 2 `748b6b5` via R54, both on main. Obsolete: the held proposal text below and the prototype `Output/r52_part2/r52_part2.patch`, superseded by R54's wording and the R61 naming rule (no 'tarjoaja'). Before the audit: **Part 1 done** with R53's decisions (see R53), live 2026-10-11. **Part 2 done** with R54's changes (see R54), live 2026-10-11. As proposed and held before R54: Check: contract length (SOPIMUS row) and utilisation (KÄYTTÖASTE) are covered; equipment owner is covered by the LAITTEET risk box (the owner on every model page); building owner and who pays electricity are missing; the provider's vacancy risk is only on the model pages. Proposal, wording from each model page's own OMISTAA table and "Sähkön hinta" risk item: row RAKENNUKSEN OMISTAA (after KERROKSET): "Pilvipalveluntarjoaja tai kiinteistösijoittaja" / "GPU-pilvi, operaattori tai kiinteistösijoittaja" / "Operaattori tai kiinteistösijoittaja" (3 and 4) / "AI Oy"; row SÄHKÖN MAKSAA (after SOPIMUS · HINNOITTELU): "Pilvipalveluntarjoaja: sisältyy hintaan" / "Yleensä GPU-pilvi: sisältyy hintaan" / "AI Oy: operaattorin laskulla (kW tai kWh)" / "AI Oy: läpilaskutettuna tai omalla sopimuksella" / "AI Oy: suoraan, usein PPA-sopimuksella"; terms note adds "käyttöaste = kuka maksaa, jos varattu kapasiteetti jää käyttämättä; vuokraamattoman tai myymättömän kapasiteetin riski on vastapuolella." Prototype with registry entries and the glossary-tag count (13 to 15): `Output/r52_part2/r52_part2.patch`, all checks green on it, not applied to main |
| R53 | 2026-10-11 | "R52 Part 1 decisions: 1. 1a, 1b, 1c approved. Include the Finland line in 1a, but correct it: the subsidy scheme is no longer planned. The government decided on 5.12.2025 on a ten-year tax-relief aid scheme from 1.7.2026, then dropped it on 1.9.2026 in the 2027 budget talks (Valtioneuvosto 5.12.2025; Reuters via The Star, 2.9.2026). The lower rate ended in June 2026. Write it in the past tense and verify the rates (0.05 → 2.24 c/kWh) on vero.fi. Add a review date to the line. 2. Examples approved with fixes: Energy, Finland: drop TVO (Mankala model, produces at cost for its shareholders, not a supplier to data centres). Use a producer with a public data-centre PPA in Finland, or Fortum alone. Cooling, Finland: Caverion only under Construction (installation contractor, same Mäntsälä contract). Leave Finland empty under Cooling unless you find a real cooling supplier, the same rule as Equipment and Storage. Prefer the customer's own source over vendor-written case studies; otherwise label them ('Nordcloud reference') or drop them. Operator, Finland: add Equinix (Helsinki) if verified. 3. Config names: short display names via a new display-name field. Do it after Monday's R45 merge, together with the render.py card anchors. 4. Neocloud: build it as proposed, but date the Nebius–Microsoft figure or leave it out of the box text. Build Part 1, keep all checks green, then commit, push, run workflow_dispatch and verify live without waiting for me. Send live screenshots and start Part 2." | **done** (audited 2026-10-21, R67): 1, 2, 4 `946b036`, `48e9571`; 3 `17c33ed`, `308d8d3`, tests `e4a7648`, all on main; check_ecosystem.py 193/193 against the live site (2026-10-21). Before the audit: **1, 2, 4 done:** `946b036` (page, data `ecosystem-data.v9.js`), `48e9571` (checks); manual run 38131079828, live 2026-10-11. Live: root, ecosystem.html, the v9 data file and business-models/ 200, no NaN; check_ecosystem.py 191/191 against the live site. Rates verified on vero.fi (0.05 c/kWh class II until 30.6.2026; 2.24 c/kWh class I from 1.7.2026). Correction to the brief: The Star's 2.9.2026 article is a Xinhua wire story, not Reuters; the source is labelled "The Star (Xinhua)". Shared poster boxes draw one money arrow per pair of boxes and none inside a box (a hyperscaler paying a GPU cloud is listed on the card only). The Nebius–Microsoft agreement is in the relationship text, dated (announced September 2025), not in the box text. **3 done** (R59 item 5): `17c33ed` (config.DISPLAY_NAMES, generated dashboard-companies.js, ecosystem Examples listing the companies with links to the dashboard cards), `308d8d3` (card anchors), tests `e4a7648`; manual run 39476131014, live 2026-10-20 |

| R54 | 2026-10-11 | "R52 Part 2 approved with three changes: 1. Keep the retail matrix cell ("AI Oy: operaattorin laskulla (kW tai kWh)"), and correct the retail model page's electricity-price risk item to match, so hub and page agree: in retail, power is billed per kW or kWh as part of the price, not necessarily at cost; pass-through fits wholesale (Digital Realty: utility costs recoverable from tenants). Register the edit in port_deviations. 2. Oma DC cell: "AI Oy: suoraan sähkönmyyjältä; suuret toimijat usein myös PPA:lla" (same nuance as R26: bought via a supplier or the market; a PPA fixes the price). 3. Terms note: "…vuokraamattoman tai myymättömän kapasiteetin riski on palveluntarjoajalla (operaattorilla tai pilvipalveluntarjoajalla)." Quote the exact 10-K passages in the ledger before committing, as you said. Then apply, run all checks, commit, push, workflow_dispatch and verify live without waiting for me." | **done:** `5103795` (this row with the passages, before the change), `748b6b5` (hub rows, terms note, retail risk item, registry entries, glossary-tag count 13 to 15); manual run 38136755045, live 2026-10-11. Live: root, ecosystem.html, the hub and the retail page 200, no NaN; check_layout_sweep (hub, retail) and check_interactions (hub 59/59, cards 229/229, pages 280/280) pass against the live site. The matrix grows 94px at 1680 (493 to 587) and 127px at 1280 (601 to 728: the own data center's electricity cell wraps to four lines there). 10-K passages, quoted from the filings on sec.gov (2026-10-11): **Microsoft FY2026** (Item 2): "We own and lease other facilities domestically and internationally, primarily for offices, datacenters, and research and development." **CoreWeave FY2025** (MD&A): "Cost of revenue primarily consists of direct costs for data centers, including costs associated with our facilities, such as rent, utilities including power, and depreciation and amortization, including depreciation of power installation and distribution systems, …"; (Item 2): "we lease space to operate data centers worldwide, including in the United States, the United Kingdom, Spain, Sweden, and Norway." **Equinix FY2025** (Item 1): "These offerings are typically billed based on the space and power a customer consumes in our IBX data centers."; (risk factors): "In certain cases, we must commit to power purchases before an IBX center is fully operational, increasing fixed costs and the risk that these costs cannot be passed on to customers."; (MD&A) contract term "generally one to five years in length"; "The cabinet utilization rate represents the percentage of cabinet space billed versus total cabinet capacity, taking into consideration power limitations." **Digital Realty FY2025**: "We control our costs by negotiating expense pass-through provisions in customer agreements for operating expenses, including power costs and certain capital expenditure." Google's Hamina PPAs: Energy Digital (2018), not a 10-K. URLs: msft-20260630.htm, crwv-20251231.htm, eqix-20251231.htm, dlr-20251231x10k.htm under sec.gov/Archives/edgar/data/ |
| R55 | 2026-10-11 | "Add to CLAUDE.md as a standing rule: once a change is approved (or needs no approval), commit, push and deploy it right away (manual workflow_dispatch if the workflow has no push trigger), then verify live. Don't hold finished changes for the next scheduled run. Approval gates in this file still apply before committing." | **done:** CLAUDE.md, "Deploy status" |
| R56 | 2026-10-11 | "Do the two queued follow-ups now (they're a live inconsistency, not polish): align the own-data-center page's electricity wording with the hub cell ("AI Oy: suoraan sähkönmyyjältä; suuret toimijat usein myös PPA:lla"), and remove or fix the unused "Pass-through" term on the retail card. Register in port_deviations, run all checks, commit, push, workflow_dispatch, verify live." | **done:** `554c81e`; manual run 38139236260, live 2026-10-11. Own data center page: the money flow ("liittymä ja siirto; sähkö suoraan sähkönmyyjältä, suuret toimijat usein myös PPA:lla"), the key-contracts row ("sähköliittymä ja sähkösopimus (suurilla toimijoilla usein myös PPA)") and the electricity-price risk item (the hub cell's wording). Grid connection and transmission are kept apart from the electricity, since they come from the network company. Retail card: Pass-through removed from KORTIN TERMIT (removed rather than reworded, so no new text; the grid now has 9 terms, one empty slot). Live: both pages, the hub, ecosystem.html and the root 200, no NaN; check_layout_sweep (both pages) and check_interactions cards 229/229 pass against the live site. The remaining "sähkön ostosopimus" on the page is the PPA term's own definition. Ray: "R56 approved as is, including the separate grid-connection wording." |
| R57 | 2026-10-11 | "Add the 10th term to the retail term box, registered in port_deviations: "kW ja kWh — kW kertoo varatun sähkötehon eli kuinka paljon sähköä laitteet voivat ottaa kerralla; kWh kertoo käytetyn energian määrän. Retail-colocationissa hinta perustuu usein varattuun tehoon (kW), ja käytetty energia (kWh) voidaan laskuttaa erikseen." Run all checks, commit, push, workflow_dispatch, verify live." | **done:** `07dfdd1`; manual run 38141598370, live 2026-10-11. Term name "kW ja kWh", the rest as the definition, in Pass-through's former slot (registered as a replacement of the source's Pass-through term). Live: retail page, hub, ecosystem.html and the root 200, no NaN, 10 terms on the card; check_layout_sweep (retail) and check_interactions cards 229/229 pass against the live site. The definition is the longest in the box: 6 lines at 1680, 8 at 1280, so the second term row is taller than the first |
| R58 | 2026-10-11 | "Ship R45 now instead of waiting for Monday: merge r45-input-fixes (model_version 2), run all checks, commit, push, workflow_dispatch, and do the before/after against the current live page (same session, Fri Oct 9 close). Report per sub-layer and any colour change. Monday's run then only does the R33b check (was an unfinished bar dropped?)." | **done:** merged `401e7b8` (the R45 branch, model_version 2; `6addb87` logged this row), manual run 38142625033, live 2026-10-11 13:18 UTC. All checks green on the merge (check_confirmation 96/96, the four checks). Before = live page from run 38141598370 (model 1, fetched 13:03 UTC); after = run 38142625033 (model 2, fetched 13:18 UTC); same session, Fri Oct 9 close. Replays on inputs frozen at 13:12 UTC (`Output/r58_before_after/`): model 1 reproduces the before page and model 2 the after page within 0.05, so the change is the code. Per sub-layer, before -> after (code effect on identical inputs): cooling 37.4 -> 36.0 (-1.36), networking 39.5 -> 38.6 (-0.88), optical 43.7 -> 44.4 (+0.77), compute 29.6 -> 29.6 (+0.02), colocation 32.1 -> 29.6 (-2.51). No colour change: all five Green before and after. Price-based page fields identical. Run log: session 2026-10-09, yfinance 1.7.0 as pinned, no format-break or error lines (the analyst exemption is gone). Monday's session job now does only the R33b check (session-only cron e188a831, replacing 2a6b3ce6) |
| R59 | 2026-10-15 | "Status first, in two lines: is R45 live, and what did Monday's R33b check show? Then, in this order, commit + push + workflow_dispatch + verify live after each: 1. Persistence (R33a/c/g, already approved): data branch with job split (only the save job has contents: write), entries dated by session, audit log one entry per ticker per session with model_version, missing sessions named never 0, CI fails loudly on an unreadable file. Then confirmation switches on as approved. Report the first two live runs: the notes, the "vs <date>" label and the heat trail filling. 2. The heading "Data center infrastructure — signal scores" is nearly invisible (same bug as the parent). Make it a proper section heading: dark navy, about 20px, bold, styled in CSS rather than inline. 3. Per-ticker rows: "VRT ▲ −6.9%" reads as a contradiction. Label the percentage with its period (e.g. "30d") and make clear what the arrow means (rating forecast), e.g. by moving it next to the rating badge or adding a legend/tooltip. Show me the wording. 4. The chain bar's "Easing: Colocation": with no history, trend words aren't supported. Until confirmation has history, show "Lowest score: Colocation" (or similar); use Easing/Emerging only when history supports a direction. Show me the wording. 5. R53.3: short display names, card anchors, and the dashboard's link cards in the new style (as on the ecosystem page). Batch the wording for 3 and 4 into one approval message; everything else needs no approval." | **done:** 1, 2, 5 below; 3 and 4 shipped under R63 with Ray's changes (live 2026-10-21, see R63). Was: 3, 4 held for Ray's approval of the wording (sent 2026-10-20). 1: `b924eb9`, `238e4dd`, tests `48717dc`, data branch `807a7c9`; run 1 = 38795478655 (2026-10-15 19:38 UTC, session Wed Oct 14): restored 0 sessions, notes "Latest session only — not yet confirmed (0 of 2 earlier sessions stored)" on all five cards, no vs label, heat trail 1 day, no colour change against the same session's page before (compute 29.5 -> 28.3 from one fewer news hit); run 2 = 38799773829 (2026-10-15 20:10 UTC, session Thu Oct 15): "(1 of 2 earlier sessions stored)", "vs Wed Oct 14", heat trail 2 days (reconstructed 2026-10-20 from the data branch with the real _confirmed_color/label code, which reproduces the live page of Mon Oct 19 exactly). From the third stored session (Mon 2026-10-19's run, session Fri Oct 16) confirmation is active: all five "Kept Green ...", the single-session page line gone. 2: `58084da`, live with run 38799773829 (h2, 20px, 700, #0E1628). 5: `17c33ed`, `308d8d3`, tests `e4a7648`; run 39476131014, live 2026-10-20: #layer-<id> opens the card, the ecosystem links land on it, link cards in the new style; check_ecosystem 193/193 against the live site. Status line given 2026-10-15: R45 live since 2026-10-11 13:18 UTC (run 38142625033), and every run since (the four scheduled runs Mon-Thu) built `2eb91d3`, model_version 2. R33b: the Monday job never fired (session-only, the session had ended), so the logs were checked on 2026-10-15. Monday's run (38306911530) started 20:51 UTC, after the close: nothing to drop, session Mon Oct 12. Tue (38449916026, 18:49 UTC), Wed (38598267866, 16:27) and Thu (38767353344, 16:14) ran during trading hours: yfinance returned that day's unfinished bar every time, and it was dropped for ^GSPC, all 12 tickers and ^VIX/^TNX/^IXIC, so each run scored the previous session. Three manual runs on 2026-10-11 at 16:10-16:26 UTC (38154353001, 38155118928, 38155471253) weren't started from this session |
| R60 | 2026-10-20 | "New ledger row: the layered responsibility view for the business-models hub. The brief (version 2) is in docs/briefs/layered-responsibility.md; read all of it. Build it as written, with these corrections: 1. Retail footnote: replace "power is usually passed through" with "sähkö laskutetaan yleensä operaattorin laskulla (kW tai kWh)". Pass-through is wholesale (consistent with R52/R57). 2. GPU cloud: make the typical demarc and cell 4 agree. Either typical line at Z1/Z2 with the range down to Z2/Z3, or cell 4 = "Itse (bare metal) / GPU-pilvi (hallittu)". Tell me which you chose. 3. Row 14: "Rakennus- ja ympäristöluvat" (zoning is the municipality's), or mark kaava as the municipality's on that row. 4. Note under the staircase: "GPU-pilvessä kapasiteetti varataan usein omaan käyttöön…". 5. Naming rule site-wide: search all business-models pages for "palveluntarjoaja"/"tarjoaja" and include every replacement in the approval message. Before building, check the cell table and the note against the five model pages and the hub matrix (contract lengths, electricity, ownership) and report any contradiction. Verify the Mäntsälä fact with a source. Build Part A as vector SVG per the brief, register all new Finnish text in port_deviations, extend the checks, and send me ONE approval message with all new and changed text plus screenshots at 1680 and 360. After approval: commit, push, workflow_dispatch, verify live." | **superseded by R61** (2026-10-20): Ray saved the brief as docs/briefs/layered-responsibility.md and restated the request with the image as the Part A stack. Was blocked: the brief wasn't available (checked 2026-10-20); nothing was built under this row |
| R61 | 2026-10-20 | "New ledger row: the layered responsibility view for the business-models hub. Read docs/briefs/layered-responsibility.md (version 2) in full and build it, with these changes: Image: - Use docs/briefs/datakeskus-kerrokset-original.png as the Part A stack (not a drawn SVG; it has the six levels in the right order). Update the brief's build-approach section to say so. - Convert to WebP, self-host it in the explainer's assets, and report its pixel width (if under 2560 px, tell me and keep going). - Overlay an SVG with the same viewBox as the image's pixel size. Zones, highlights, labels, the demarc line in the gaps between slabs and the clickable zone buttons all live in the SVG; nothing is baked into the image. Measure the zone polygons on this final file and store them in the data file; the image is frozen. - Z4 polygon around the caged racks only (the white units on that floor read as in-row cooling; row 8 stays in Z5). - Connection-point marker at the pylons/substation fence; waste-heat hotspot on the red/blue pipe toward the town. - Check the full-size image for text-like marks and report any. Add Finnish alt text. Content corrections: 1. Retail footnote: "sähkö laskutetaan yleensä operaattorin laskulla (kW tai kWh)" instead of "passed through" (pass-through is wholesale; consistent with R52/R57). 2. GPU cloud: make the typical demarc and cell 4 agree. Either typical line at Z1/Z2 with the range down to Z2/Z3, or cell 4 = "Itse (bare metal) / GPU-pilvi (hallittu)". Tell me which. 3. Row 14: "Rakennus- ja ympäristöluvat" (zoning is the municipality's). 4. Note under the staircase: "GPU-pilvessä kapasiteetti varataan usein omaan käyttöön…". 5. Naming rule site-wide: search all business-models pages for "palveluntarjoaja"/"tarjoaja" and include every replacement. Before building, check the cell table and the note against the five model pages and the hub matrix and report any contradiction; verify the Mäntsälä fact with a source. Register all new Finnish text in port_deviations and extend the checks. Then send me ONE approval message with all new and changed text plus screenshots at 1680 and 360. After my approval: commit, push, workflow_dispatch, verify live." | **done:** `972ea5e` (brief v2 with the build approach updated, and the source PNG), `6933f94` (section, matrix, naming, registry), `a3e4dc7` (checks: suite layers); manual run 39565308206, live 2026-10-21. Approved with changes (R62). Contents: business-models/index.html (section, matrix without the KERROKSET row, naming), assets/datakeskus-kerrokset.webp (1672x941, 485 KB, from the PNG, frozen), assets/kerrokset-data.js (measured polygons, gaps, markers), assets/kerrokset.js, specialised-models.html (#hukkalampo), public-cloud.html, gpu-cloud.html and glossary-fi.js (naming), tools/port_deviations.json, tools/check_interactions.py (suite layers), docs/briefs (brief, build approach updated; the PNG). GPU cloud: option B (cell 4 'Itse (bare metal) / GPU-pilvi (hallittu)', typical line Z2/Z3, range up to Z1/Z2). Mäntsälä verified: DCD 2015, Sitra, Nebius |
| R62 | 2026-10-21 | "R61 approved with two changes: 1. One colour convention on the hub page: the company is navy in both the new section and the table below (AI Oy's risk boxes), the counterparty light blue. If that hurts the table's readability, show me the alternative before committing. 2. Waste heat body, first two sentences: "Datakeskuksen omistaja tai operaattori voi myydä palvelinten hukkalämmön kaukolämpöyhtiölle. Mäntsälän datakeskus on myynyt hukkalämpöä paikalliseen kaukolämpöverkkoon vuodesta 2015; sen rakensi Yandex, nykyään se on Nebiuksen." The Microsoft–Fortum sentence stays. Register the changes in port_deviations, run all checks, then commit, push, workflow_dispatch and verify live. Send live screenshots at 1680 and 360. Queue (not now): a 2× upscale of the stack image (geometry unchanged, coordinates scale with it). Also resend me the R59 items 3–4 wording approval message." | **done:** in `6933f94` (risk boxes and legend swatches on the hub: the company navy #12222E, the counterparty light blue #E8EFF5, as in the section; text contrast 16.2:1 and 7.6:1, so no alternative was needed; the waste-heat text with Ray's two sentences, registered), checks `a3e4dc7`; manual run 39565308206, live 2026-10-21. Live: the hub, its assets, the specialised-models anchor and the model pages 200, no NaN on the dashboard; check_interactions (hub 59, cards 229, pages 280, layers 57) and check_layout_sweep (hub, specialised models, public and GPU cloud) pass against the live site; the brief is not deployed (404). Upscale queued. R59 items 3-4 wording resent 2026-10-21 |
| R63 | 2026-10-21 | "R59 items 3 and 4 approved with changes; ship each with a deploy and live check. 3. As proposed, plus: legend "▲ ▼ — revenue growth speeding up / slowing / steady · 30d = share price change over 30 days"; tooltips say "5 percentage points", not "5 points". 4. As proposed, plus the same rule at the top end: if no sub-layer is Red or Orange, show "Highest score: <name> (<score>)". So without confirmed Red/Orange/Blue the bar reads "Highest score: … · Lowest score: …". 5. Also now (from the queue): when the latest colour is Green and the last 3 sessions were all Green, the note reads "Green, steady: also Green in the last 3 sessions" instead of "Kept Green … isn't confirmed yet". Keep the other note variants as they are. Check which cards on the live page currently show the old wording and report. Register user-facing text as usual, run all checks, commit, push, workflow_dispatch, verify live, and send screenshots." | **done**, each item shipped with its own deploy and live check on 2026-10-21. Live before (session Tue Oct 20, run 39565308206): all five cards showed "Kept Green: latest score … isn't confirmed yet, and recent sessions were mostly Green". 3: `05bbe8a`, tests `57af51a`; run 39581166237 (rows "30d …", key line, arrow tooltips in percentage points, "Revenue growth"). 4: `c198fbc`, tests `31e34a0`; run 39582219184 (live bar: "Highest score: Optical (44) · Lowest score: Colocation (28)"; Bottleneck/Emerging/Easing only from colours backed by stored history). 5: `4868b7b`, tests `6070f4d`; run 39583615091: all five cards now "Green, steady: also Green in the last 3 sessions". The steady rule reads the stored colour, which is the one the card showed after confirmation (main.py sets best["color"] from _confirmed_color, render.save_scores_history stores it), not a score in the Green band; a test with a Green-band score shown Orange keeps the holding note. Checks: confirmation 129/129, the four page checks green before each commit; live: root, ecosystem.html, business-models/ 200, no NaN. The dashboard's text isn't in port_deviations (that registry covers the explainer); its new wording is pinned by check_confirmation.py |
| R64 | 2026-10-21 | "New ledger row, to start AFTER the R61 round-2 row is live (don't mix them): reliability, network ecosystem and an analogy for the business-models explainer. Verify every fact with a source, register all Finnish text in port_deviations, and send me ONE approval message with all new text before committing. … 1. Layered view, one sentence under the lede (factory analogy) … 2. Layered view legend, one line (SLA covers what is below the responsibility line) … 3. Z5 zone panel: kahdennus (N+1, 2N) … only say 'rakennuksen investoinneista' … 4. Note under the staircase, add (retail network ecosystem; wholesale: power, land, cooling) … 5. Retail model page: a short paragraph on the network ecosystem … Draft it and show me. 6. Glossary entries (check which already exist): SLA / käytettävyys with the table 99,9 % ≈ 8 h 46 min, 99,99 % ≈ 53 min, 99,999 % ≈ 5 min … kahdennus (N+1, 2N); cross-connect; verkkoekosysteemi; Tier-luokitus (Uptime Institute) only if you can define it accurately from the source. 7. Only if a reliable source supports it: one sentence that AI training halls may be built with less redundancy … Do not add: the AI value-chain stack (agent/API/inference), or unsourced cost-of-outage claims." (Full proposed Finnish text in Ray's message of 2026-10-21; quoted in full in the approval message.) | **done, live 2026-10-21** (manual run 39600529929): item 1 `168eeb8`, 2 `9b2aeaf`, 3 `e2f6e57`, 4 `c8d8a69`, 5 `cc7af75`, 6 `d6ebdd9`; item 7 left out (no reliable source). Live: check_interactions (hub 59, cards 229, pages 280, layers 58) and check_layout_sweep clean against the live site; root, hub, retail, glossary 200. Approved 2026-10-21 (Ray: "R64 approved as you proposed, including the optional fix: 'Retail-colocationin arvoa lisää myös verkkoekosysteemi…'. Build and ship it as planned (register strings, five checks, commit item by item, push, workflow_dispatch, live screenshots)."). Sources checked and text drafted; adjustments for items 2, 3 and 4 where sources required; item 7 left out (no reliable source). "The R61 round-2 row" was asked about rather than guessed: Ray, 2026-10-21: it is NOT R62 but a new row he hadn't sent; logged as R65 |
| R65 | 2026-10-21 | The "R61 round-2 row", sent 2026-10-21, to do right after R64: "1. Zone fills in the image overlay, per selected model: 'Itse' zones translucent navy, counterparty zones a light wash, shared/'riippuu palvelusta' hatched, matching the legend under the image. Remove the black outline stroke around Z1. Switching tabs must visibly grow the dark share downwards; keep labels readable on top of the fills (contrast check). 2. Each model tab gets a small vertical 6-segment bar (Z1 at the top), with the 'Itse' segments dark and shared ones hatched, so the tab row reads as a staircase at a glance. Accessible name unchanged; the bar is aria-hidden. 3. Side panel default state: replace 'Valitse kerros kuvasta tai listasta.' with the selected model's summary; clicking a zone shows the zone details as now, with a way back to the summary. Texts (register in port_deviations; check each against the cell table and report any mismatch): - Julkinen pilvi: 'Yritys hoitaa sovellukset ja datan. CSP hoitaa kaiken muun palvelimista kiinteistöön.' - GPU-pilvi: 'Yritys hoitaa sovellukset, datan ja käyttöjärjestelmän, usein myös klusterin hallinnan. GPU-pilvi hoitaa laitteet, konesalin ja kiinteistön.' - Retail-colocation: 'Yritys omistaa ja hoitaa palvelimensa ja verkkolaitteensa. Colocation-operaattori hoitaa räkkitilan, sähkön, jäähdytyksen ja kiinteistön.' - Wholesale-colocation: 'Yritys vuokraa kokonaisen salin ja kalustaa sen. Turnkey-mallissa operaattori hoitaa jäähdytyksen, UPS:n ja varavoiman; powered shell -mallissa yritys rakentaa nekin itse, ja vuokranantaja tarjoaa rakennuksen ja sähköliittymän.' - Oma datakeskus: 'Yritys hoitaa kaiken tontista sovelluksiin. Verkkoyhtiön vastuu päättyy liittymispisteeseen.' 4. The connection-point and waste-heat labels get the same white label boxes as the zone callouts. 5. Cloud range: draw 'PaaS ja SaaS' / 'hallittu palvelu' as a light shaded band between the typical line and the range end, not a thin dotted line. 6. Do the 2× upscale of the stack image now (geometry unchanged; scale the coordinates and verify the zones against the new file). Keep the zone list as is. Extend the layers suite (fills per model, tab bars, default summaries). If a summary text needs changing, send me only those changes for approval; otherwise ship: commit, push, workflow_dispatch, verify live, and send screenshots at 1680 (all five tabs) and 360." | **done, live 2026-10-21.** 3 `3aa79ca` (manual run 39609085830): the panel opens on the model's summary, '← Takaisin yhteenvetoon' returns to it; live check_interactions (layers 80/80, hub, cards, pages) and check_layout_sweep clean. 1, 2, 4, 5 (manual run 39604841545): 1 `a271375` (fills; own zones translucent navy, no outline at rest; fill staggered top-down when the Itse share grows), 2 `0ede06c` (tab bars, aria-hidden), 4 `bd15d17` (marker label boxes), 5 `dcd11e5` (range band, dotted edge removed); tests `db4ac98`. Live: check_interactions (layers 74/74, hub, cards, pages) and check_layout_sweep clean; lowest label contrast 5.3 (worst case over black). **3 approved** (Ray, 2026-10-21: "R65 item 3 approved with your corrected texts (Julkinen pilvi, GPU-pilvi, Wholesale-colocation as you proposed; Retail and Oma datakeskus as originally written) and the '← Takaisin yhteenvetoon' button. Register in port_deviations, run all checks, commit, push, workflow_dispatch, verify live."). **6 closed without upscaling** (Ray, 2026-10-21: "Item 6: close it without upscaling. No larger source exists and the gain doesn't justify invented detail. Remove it from the queue; note in the ledger that a 2× version would only come from regenerating the image (with re-measured zones), if ever needed."). The original PNG is 1672x941; a 2x version would only come from regenerating the image, with every zone in assets/kerrokset-data.js re-measured, if ever needed |
| R66 | 2026-10-21 | Cloud service models ("this was the round-2 amendment; it didn't make it into R65"): "A. On the Julkinen pilvi tab, mark three named positions on the cloud range band: IaaS at the Z1/Z2 line (typical; company manages the OS), PaaS inside Z1 (company handles only its code and data), SaaS at the top (company uses the application and handles its own data and access). Keep the shaded band. GPU-pilvi keeps its 'hallittu palvelu' range. B. Glossary entries (unless they exist; if so, show me the differences). No 'tarjoaja', no product names: - IaaS (Infrastructure as a Service): 'Pilvipalvelu, jossa yritys vuokraa virtuaalipalvelimia, tallennusta ja verkkoa. CSP hoitaa konesalin, laitteet ja virtualisoinnin; yritys hoitaa käyttöjärjestelmän, ohjelmistot ja datan.' - PaaS (Platform as a Service): 'Pilvipalvelu, jossa CSP hoitaa myös käyttöjärjestelmän ja ajoympäristön; yritys vastaa omasta koodistaan ja datastaan.' - SaaS (Software as a Service): 'Valmis sovellus pilvipalveluna. CSP hoitaa sovelluksen ja kaiken sen alla; yritys vastaa omasta datastaan ja käyttäjien pääsyoikeuksista.' - GPUaaS (GPU as a Service): 'GPU-laskentakapasiteetin vuokraus palveluna. Tällä sivustolla mallia kutsutaan nimellä GPU-pilvi.' Link IaaS/PaaS/SaaS in the cloud note and the range labels to these entries. Check they agree with the cell table and the new public-cloud summary; report any mismatch. If the wording needs no change, ship without asking: register, checks, commit, push, workflow_dispatch, verify live, screenshot of the public-cloud tab at 1680." | **A done, live 2026-10-21:** `ab1b681` (manual run 39611274597; new gap g1t near the top of Z1; IaaS g12, PaaS g1x, SaaS g1t, band g1t-g12); live check_interactions (layers 85/85) and layout sweep clean. **B done, live 2026-10-21:** `b5b1e11` (manual run 39614673310): IaaS, PaaS, SaaS and GPUaaS replace the combined entry (75 glossary entries), card 1's key row links each; the cloud note and the band labels link to them (glossary.js dispatches a click for SVG terms on Enter); live check_interactions (layers 86/86, hub 59/59 with 23 tagged terms) and layout sweep clean. No mismatch with the cell table or the summary (SaaS is the band's top end, beyond the typical IaaS position the table shows). Approved (Ray, 2026-10-21: "R66 B approved as you recommend: replace the combined 'IaaS, PaaS ja SaaS' entry with the four separate entries, split card 1's key-row link into IaaS / PaaS / SaaS, keep card 1's short term box. One harmonisation: in the IaaS entry use 'virtuaalikoneita' instead of 'virtuaalipalvelimia' (the site's established term). Link IaaS/PaaS/SaaS in the cloud note and the three band labels." ... "Ship both: checks, commit, push, workflow_dispatch, verify live.") |
| R67 | 2026-10-21 | "Ledger audit (read-only first): for R16, R29, R33, R36, R43, R48, R52 and R53, check each open or partial item against the repo and the live site, and report what's actually done, still open or obsolete. Then update the statuses in one docs commit, with evidence (commit hash from command output, or what you checked live). Don't build anything in this row; list any genuinely open work for me to decide." | **done:** audit reported 2026-10-21; all eight rows done, statuses updated with evidence in this commit; open work listed for Ray under R16 |
| R68 | 2026-10-21 | "Fine-print dating: yes, apply the R16 convention consistently. Add 'tarkistettu 10/2026' to the fine print of the retail card (R54 electricity, R64 Equinix figures), the own data center card (R56) and the hub (R54 matrix rows), and to the source lines of the hub's waste-heat and Z5 panels. Page-level labels stay 9/2026. Register in port_deviations." "Ship both: checks, commit, push, workflow_dispatch, verify live." | **done, live 2026-10-21:** `1d2bf5b` (manual run 39614673310): dated source sentences in the fine print of the retail card (Equinix FY2025 10-K), the own data center card (Google's PPAs in Finland, 2018 and 2026) and the hub (R54's four 10-Ks), each with its URLs in an HTML comment; ' · tarkistettu 10/2026' on the hub's waste-heat and Z5 source lines; page labels stay 9/2026. Live: all three pages carry the date; check_interactions and layout sweep clean |
| R69 | 2026-10-21 | "New ledger row: clarity round for the layered view. 1. Zone names (image callouts, zone list, side panel, screen-reader labels, staircase hover links): Z3 "Palvelimet ja verkko" → "IT-laitteet"; Z4 "Palvelinsali" → "Salitila ja räkit". Other zone names unchanged. Update the brief and port_deviations. 2. One-line description at the top of each zone panel, before the row list (the Z5 redundancy text follows its line): - Sovellukset, data ja ohjelmistot: "Se, mitä varten kapasiteettia tarvitaan: sovellukset, tekoälymallit, niiden data ja käyttöjärjestelmä." - Ohjelmistoalusta: "Kerros, joka jakaa laitteiden kapasiteetin käyttöön: virtualisointi ja klusterin hallinta." - IT-laitteet: "Laitteet, jotka tekevät varsinaisen laskennan ja tallennuksen: palvelimet, tallennusjärjestelmät ja verkkolaitteet." - Salitila ja räkit: "Tila, johon IT-laitteet asennetaan: räkit, häkit ja sähkönsyöttö räkkiin. Täällä ei itse lasketa mitään." - Rakennuksen tekniikka: "Järjestelmät, jotka pitävät salin käynnissä: jäähdytys, UPS, varavoima ja kulunvalvonta." - Kiinteistö ja liittymä: "Tontti, rakennus, sähköliittymä ja muuntamo, sähkön hankinta ja luvat." Check each against the zone↔row mapping and the cell table; report any mismatch. 3. Counterparty clarity: in each model summary, name the counterparty in full with 2–3 examples taken only from the ecosystem page's already-sourced examples (e.g. public cloud: "pilvipalveluyhtiö (CSP), esimerkiksi Microsoft, Google tai Amazon"). Make every "CSP" label in the callouts and zone list a glossary-linked abbreviation with a tooltip ("CSP = pilvipalveluyhtiö, cloud service provider"). 4. Selected-zone highlight: use the same accent colour as the selected list item instead of the thick black outline. 5. Nudge the "Vastuuraja, tyypillisesti" label so it doesn't sit on the Ohjelmistoalusta leader line. 6. Legend key: "Jaettu tai riippuu palvelusta" → "Jaettu tai riippuu palvelusta tai sopimuksesta" (wholesale Z5 depends on the contract type). 7. The note under the staircase: same content, formatted as a short list instead of one paragraph: - "Julkinen pilvi ja GPU-pilvi: ero on ennen kaikkea sitoumuksessa. GPU-pilvessä kapasiteetti varataan usein omaan käyttöön monivuotisella sopimuksella." - "Retail ja wholesale: ero on mittakaavassa ja sopimuksessa. Wholesale on kokonainen sali tai rakennus 5–15 vuoden vuokrasopimuksella." - "Retail-colocationin arvoa lisää myös verkkoekosysteemi: samassa rakennuksessa toimivat operaattorit ja pilvipalvelut, joihin voi kytkeytyä suoraan (cross-connect). Wholesale-asiakkaalle tärkeämpiä ovat sähkökapasiteetti ja jäähdytys." - "Pilvimalleissa vastuuraja riippuu myös ostetusta palvelusta." Keep the lead sentence "Kerrokset eivät näytä kaikkia eroja." above the list. 8. Trim the Z1 polygon to the area of the floating panels, so it no longer reads as a grey roof over the cloud. If any text needs changing after your checks, send me only those changes; otherwise ship: register, checks, commit, push, workflow_dispatch, verify live, screenshots of the public-cloud, retail and wholesale tabs at 1680 (one with a zone selected)." (Ray noted, not part of the row: leave wholesale Z6's list label as it is.) | **done, live 2026-10-21** (manual run 39649300460): items 1-2 `91d099d` (Z3 'IT-laitteet', Z4 'Salitila ja räkit', brief updated; one-line description per zone under the panel title, all six match the zone-row mapping and the cell table); 3 `51bd0e3` (summaries name the counterparty with examples from the ecosystem page's sourced lists: hyperscaler Microsoft/Google/Amazon, neocloud CoreWeave/Nebius/Lambda, operator Equinix/Digital Realty/Telia, TSO/DSO Fingrid/Caruna; CSP in callouts and zone list is a hover-only glossary term inside the zone's button, the side panel's CSP the keyboard-reachable one); 4-5 `dc0c290` (one selection colour, blue #1F4E6E, for the selected zone and list item, hover the lighter blue; Z2's leader starts mid-edge via kerrokset-data.js 'leader', since a generic mid-edge rule put Z3's leader on retail's label; a check now keeps every line label clear of every leader on all tabs, mutation-tested against the old code); 6-7 `d581719` (legend 'tai sopimuksesta'; note as lead sentence plus four-item list); 8 `070065d` (Z1 follows the panels; the PaaS/SaaS lines shortened to stay inside). Live: check_interactions (layers 95/95, hub, cards, pages) and layout sweep clean; local runs had three transient stalls/network suspensions on unchanged pages, each passing on rerun |
| R70 | 2026-10-21 | "R69 follow-up (next free ID), two small fixes. Ship and deploy right away without asking. 1. Selected zone in the list must be visible on navy ("Itse") items. Now the blue ring (#1F4E6E) on a navy button (#12222E) is nearly invisible: in Oma datakeskus all six items are navy and you can't tell which is selected; same for retail Z2. Keep blue, but add a white gap between button and ring for all list items, e.g. box-shadow: 0 0 0 2px var(--white), 0 0 0 5px var(--blue). Apply the same to the :focus-visible state if it has the same problem. On the image, leave the zone stroke as is unless your screenshots show it equally weak on navy zones; if so, add a thin white halo under the blue stroke. 2. Wholesale summary (lr-summary, wholesale-colocation): change "Turnkey-mallissa operaattori hoitaa jäähdytyksen, UPS:n ja varavoiman;" to "Turnkey-mallissa operaattori hoitaa jäähdytyksen, UPS:n, varavoiman ja kulunvalvonnan;" so it matches Z5 and the cell table (rows 8–10). Run the interaction and layout checks against live after deploy. Screenshots (live, 1680): Oma datakeskus with Kiinteistö ja liittymä selected, and Retail-colocation with Ohjelmistoalusta selected. If the local check stalls seen in R69 happen again, log them in the queue with the suite and page names." | **done, live 2026-10-21** (manual run 39654756859): 1 `7664697` (list ring 0 0 0 2px white, 0 0 0 5px blue; the image's selection stroke was equally weak where a navy zone meets a navy neighbour, so a white halo (9px, 90% white) now sits under the blue stroke; :focus-visible keeps its rust outline with a 2px offset, which already shows on navy); 2 `0430cb3` (wholesale summary: 'UPS:n, varavoiman ja kulunvalvonnan'). Live: check_interactions (layers 95/95, hub, cards, pages) and check_layout_sweep clean. No local check stalls this round, so none logged |
| R71 | 2026-10-21 | "Fix: the "Market regime" label on the page uses different rules from the multiplier actually applied to scores. Root cause is confirmed in code: render.py computes its own label (VIX>30 or yield>100 → Risk-Off; VIX>20 or yield>50 → Neutral; NASDAQ ignored), while score_engine.get_macro_multiplier() votes across all three signals (Risk-Off needs two risk signals; Neutral needs one risk or two neutral). VIX 25 alone shows "Neutral" while scores get 1.0x; VIX 35 alone shows "Risk-Off" while scores get 0.85x. 1. First, for today's macro data, print the current render.py label and the get_macro_multiplier() regime and multiplier. Tell me whether they disagree today. 2. Make the page label use the regime and multiplier the scores actually used (already in each result's "regime"; one source, don't re-implement the rules in render.py). Show the multiplier next to it, e.g. "Market regime: Neutral · scores × 0.85". Unknown stays as is. 3. In the info text under the label, add one line stating the voting rule above, so the page explains what it applies. 4. Add a check that the rendered label equals the engine regime for: VIX 25 alone; VIX 35 alone; VIX 35 + yield +120; all three missing. Scoring is unchanged: no model_version bump, no history impact. If PLAN.md has this item, close it. Commit, push and run the workflow manually right away; report the live label." | **done, live 2026-10-21** (manual run 39657216668): `5de1389` (render.regime_label() reads the regime and multiplier from the scored results, the engine's own rule only when nothing was scored; tooltip states the voting rule), tests `e622b62` (four macro cases rendered through stage_score -> generate_dashboard; fails on the old code for VIX 25 alone and VIX 35 alone). Today (session Tue Oct 20: VIX 17.31, 10Y +14.9 bps, NASDAQ vs S&P -0.0198) both rules gave Risk-On x1.0, so no disagreement today; NASDAQ sat 0.02 points from the -2% neutral threshold. Live label: 'Market regime: Risk-On · scores × 1.00'. No PLAN.md item existed to close. Scoring unchanged |
| R72 | 2026-10-21 | "After the live label check: in the regime tooltip rule line, change "5 points behind" and "2 points behind" to "5 percentage points behind" and "2 percentage points behind" (it's the 20-day return gap, not index points). Commit, push, run the workflow right away." | **done, live 2026-10-21** (manual run 39657612739): `613d4a7`; live tooltip says '5 percentage points behind' and '2 percentage points behind'; check_confirmation asserts it (134/134) |
| R73 | 2026-10-21 | "Staircase grid (Näytä kaikki mallit rinnakkain), three fixes, next free ID. Ship and deploy right away without asking unless a text needs changing. 1. Equal column widths: the five model columns get the same width (table-layout: fixed; row-label column stays as is). Long cells wrap; break the wholesale rows 8–10 text into two lines: "Turnkey: operaattori" / "Powered shell: itse". 2. Draw the vastuuraja in the grid, same rust dashed style as the image and the legend, as a line on the top edge of the step cell: Julkinen pilvi above row 4; GPU-pilvi above row 5; Retail above row 7; Wholesale two lines, turnkey above row 8 and powered shell above row 11; Oma datakeskus none. Positions must match the image's demarc per model; add that to the layers check. 3. Selected column: remove the per-cell rust inset boxes (td.is-col). Rust is for the vastuuraja only, as in the image since R69. Mark the selected column once: header styled like the selected tab (navy, white text) and thin blue side edges on the column's cells, or an equivalent single cue in blue. Run the interaction and layout checks against live. Screenshots (live) with the grid open: 1680 with Julkinen pilvi selected, 1680 with Wholesale-colocation selected, and 390 wide." | **done, live 2026-10-21** (manual run 39660808360): `f72a22d`. 1: table-layout fixed, a 22% label column and five equal model columns; wholesale rows 8-10 show 'Turnkey: operaattori' / 'Powered shell: itse' on two lines (the ' · ' stays in the DOM, hidden, so the callouts, zone list and registry text are unchanged); below 1024px the grid's min-width is 960px (it swipes there anyway), since at 760px the equal columns made wholesale's cells wrap to four lines. 2: a rust dashed top edge at each step, derived from the same gaps as the picture's lines (public row 4, GPU row 5, retail row 7, wholesale rows 8 and 11, own none); the layers check asserts grid = picture = these rows. 3: td.is-col's rust boxes removed; the selected model's header is navy with white text and its 14 cells get thin blue side edges. Live: check_interactions (layers 98/98, hub, cards, pages) and layout sweep clean. No text changed |
| R74 | 2026-10-22 | "Repo: RayDar-DataCenter. Tiedosto: business-models/why-finland.html. Päivitä "Miksi Suomi" -sivua muuttamatta sivun rakennetta, tyyliä tai muita kortteja. 1. SÄHKÖ-kortti: lisää lause: "Eurostatin mukaan yritysten sähkö oli EU:n halvinta Suomessa 2. vuosipuoliskolla 2025 (7,48 c/kWh vs. EU-keskiarvo 18,37 c/kWh, kulutusluokka 500–2 000 MWh)." 2. VASTATUULET, uusi kortti "Rakentaminen ei ole halvempaa": "Turner & Townsendin 2026-indeksissä Helsingin datakeskuksen rakennuskustannus on 13,33 $/W. Helsinki, Tukholma, Oslo ja Kööpenhamina ovat kaikki indeksin kymmenen kalleimman joukossa." 3. VASTATUULET, uusi kortti "Talven hintariski": "Keskihinta on matala, mutta vaihtelu on suurta: vuoden 2026 yhdeksällä ensimmäisellä viikolla sähkö oli Suomessa keskimäärin kalliimpaa kuin Saksassa." 4. Korvaa "Tukipolitiikka elää" -kortin teksti: "Hallitus on linjannut enintään 30 M€/v:n kymmenvuotisen veronpalautustuen. Ehtoina ovat rekisteröityminen sekä hukkalämmön hyödyntäminen tai tiukempi energiatehokkuus. Voimaantulo on vielä auki." 5. Päivitä leimat muotoon "TIEDOT TARKISTETTU 10/2026" ja "Tilanne lokakuu 2026". Lisää lähteisiin Eurostat ja Turner & Townsend. Commitoi ja pushaa mainiin heti, ja tarkista, että GitHub Pages -sivu päivittyy." | **done, live 2026-10-22.** Items 4-5 `183da4f` (manual run 39744785385): support card 'Korvaava tuki peruttiin' with Ray's text minus 'vuotuisen' (valtioneuvosto 165/2025, Yle 5.12.2025 and Uusi Suomi 2.9.2026 say only 'enintään 30 miljoonaa euroa', no period); MAAPERÄ 'Hyvin pieni maanjäristysriski'; TIME-TO-MARKET left as it was: the Kaleva source is from 18.3.2025, and the fresher Fingrid source Ray asked for (half-year report 23.7.2026) supports the original wording ('etenkin pohjoisemmassa Suomessa liityntöjä voidaan edelleen toteuttaa kansainvälisesti vertaillen nopealla aikataululla'), so the earlier 'not found' flag was wrong; label 'TIEDOT TARKISTETTU 10/2026' and fine print 'Tilanne lokakuu 2026' after the full pass, government/Uusi Suomi/SSS sources linked. Live: pages suite 280/280, why-finland sweep clean. Items 1-3 (manual run 39742347722): `4bbb226`. Verified 2026-10-22: Eurostat 2H2025 non-household, band 500-2 000 MWh, Finland 7.48 vs EU 18.37 EUR/100 kWh, lowest in the EU (ddn-20260508-2); Turner & Townsend DCCI 2026 (2026-27) Cost trends: Helsinki US$13.33/W, Copenhagen 14.41, Oslo 13.95, Stockholm 13.92, all four in the top ten; winter: day-ahead 1.1.-4.3.2026 FI 122.0 vs DE-LU 103.5 EUR/MWh (ENTSO-E via Energy-Charts). Live: pages suite 280/280, why-finland sweep clean. **4-5 decided** (Ray, 2026-10-22: "R74 kohdat 4–5, business-models/why-finland.html. Muuta vain alla mainitut kohdat. 1. VASTATUULET, tukikortti: - Otsikko: "Korvaava tuki peruttiin" - Teksti: "Hallitus linjasi joulukuussa 2025 enintään 30 M€:n vuotuisen, kymmenvuotisen veronpalautustuen sähköveron korotuksen tilalle, mutta luopui siitä syyskuun 2026 budjettiriihessä. Sähköveron korotus jää siis voimaan täysimääräisesti." - Lähteiksi Uusi Suomi ja SSS (linkit kuten raportissasi) sekä valtioneuvoston tiedote 5.12.2025: https://valtioneuvosto.fi/-/talouspoliittinen-ministerivaliokunta-linjasi-datakeskusten-tuen-ja-rekisteroinnin-valmistelusta 2. MAAPERÄ-kortti: "Ei maanjäristyksiä" → "Hyvin pieni maanjäristysriski". Muu lause ennallaan. 3. TIME-TO-MARKET-kortti: - Otsikko: "Nopea verkkoliityntä" → "Verkossa tilaa pohjoisessa" - Ensimmäinen lause: "Fingridin mukaan kantaverkossa on tilaa etenkin Pohjois-Suomessa." - Toinen lause: "Sähkö on alan niukin resurssi, joten vapaa verkkokapasiteetti on kilpailuetu." - Tarkista Kalevan jutun julkaisupäivä. Jos se on vuodelta 2025 tai vanhempi, etsi tuoreempi Fingridin lähde (esim. liityntäkapasiteettia koskeva julkaisu 2026) ja käytä sitä. Jos tuoreempaa ei löydy, pidä Kaleva ja merkitse vuosi lähteeseen. 4. Kun 1–3 on tehty, nosta leimat "TIEDOT TARKISTETTU 10/2026" ja "Tilanne lokakuu 2026". 5. Aja sivun tarkistukset, commitoi ja pushaa mainiin heti. Merkitse R74 suljetuksi ledgeriin."). Before: **4 held:** Ray's text says the government has outlined the 30 M EUR/yr ten-year refund and that the start date is open, but the government dropped it in the 1.9.2026 budget session (Uusi Suomi 2.9.2026, SSS/Purra, AI Suomi; also R53); corrected text sent to Ray. **5 held:** R16 allows raising a page label only after a full pass of the page's facts; the pass (2026-10-22) confirmed Fingrid 99,99995 % (2025), >100 GW requests with over half data centres, Nebius PUE ~1.1 (company figure), Google-EKAMI training (Yle), the carbon-free mix and the electricity tax, but card 4 is out of date, 'Ei maanjäristyksiä' is absolute (Finland has small quakes) and Fingrid's 'kansainvälisesti vertaillen nopeasti' wasn't found in Fingrid's material; asked Ray |
| R75 | 2026-10-22 | "business-models/why-finland.html, TIME-TO-MARKET-kortti: jos lähteissä ei vielä ole Fingridin puolivuosikatsausta 23.7.2026, lisää se pienpräntin lähteisiin samaan tapaan kuin muut lähdelinkit. Älä muuta kortin tekstiä. Aja sivun tarkistukset, commitoi ja pushaa mainiin. Jos lähde on jo mukana, ei toimenpiteitä." | **done, live 2026-10-22** (manual run 39746745787): `68aac92`; the fine print reads 'Fingrid (puolivuosikatsaus 23.7.2026)' with a link, card text unchanged; port text, pages suite 280/280 and why-finland sweep clean |
| R76 | 2026-10-23 | "Ecosystem page: money flows, round 1 (next free ID). Content edit, new data file version (ecosystem-data.v10.js), per the file's own rule. Texts approved; ship and deploy right away without asking unless a text needs changing. A. Correct who buys the IT hardware (money step 3 says the operator pays for "compute and electrical equipment" and "storage systems"). 1. Split money step 3 into two steps (walkthrough becomes 8 steps): "3. The operator pays for the facility's systems" — "The operator pays the suppliers of the systems that keep the facility running: power and electrical equipment, cooling, backup power and the site's network connections." payments: operator → equipment "power and electrical equipment" [build]; operator → cooling "cooling systems" [build]; operator → cooling "maintenance and service" [operate]; operator → backup_power "generators and UPS systems" [build]; operator → backup_power "fuel and maintenance" [operate]; operator → network "connectivity" [operate]. "4. IT hardware: the biggest bill" — "Servers, GPUs, storage and network gear are bought by whoever runs the IT layer: the hyperscaler or GPU cloud, or in colocation the customer itself. In an AI data center this is by far the largest cost: Epoch AI estimates that for a 1 GW AI data center, servers are about 60% of the annualized total cost of ownership and electricity, the largest running cost, about 7%. The hardware is replaced every few years, so in practice the bill recurs." payments: hyperscaler → equipment "servers and GPUs" [build]; neocloud → equipment "GPUs and servers" [build]; enterprise → equipment "own servers, in colocation" [build]; hyperscaler → storage "storage systems" [build]; source: Epoch AI, AI data center cost breakdown (14 May 2026), https://epoch.ai/data-insights/ai-datacenter-cost-breakdown. Verify the 60% figure and electricity at $0.6B of $8.5B (about 7%). Move the Daily signals link from old step 3 to this step: "Steps 3 and 4 are the investment flow the Daily signals page tracks →". 2. Equipment description: append "Compute hardware is bought by whoever runs the IT layer (a hyperscaler, a GPU cloud or a colocation customer); the operator buys the facility's power and electrical equipment." Explorer: add equipment → hyperscaler, goods, "Servers, GPUs & network gear" (added: true). Leave poster labels. B. 3. Step 1: enterprise → operator "colocation fees: space, power and cross-connects"; description "pay data center operators for colocation space" → "pay data center operators for colocation: space, power and cross-connects (direct cable links to carriers and clouds in the same building)". 4. Energy step (now 5): operator → energy_gen "electricity, from a retailer or the exchange, often with a long-term PPA"; Energy & Power Generation description append "A data center buys its electricity from a retailer or on the power exchange; large buyers often also sign a PPA with a producer." 5. Public sector step (now 8): split the first payment into "land price and building-permit fees" [build] and "land rent, where the municipality leases the plot" [operate]. All other payments in steps 1 and 5–8 are [operate]; step 2's are [build]. 6. Life of a data center, step 6 ("Customers"): add neocloud to highlightIds; description ends ", and GPU clouds rent out GPU capacity." C. 7. Mode switch above the explorer: "Relationships" / "Money flows" (aria-pressed, default Relationships). 8. Money flows mode draws every payment from MONEY_WALKTHROUGH_STEPS, payer → payee, poster money-arrow style; a pair with several payments gets one arrow per phase, labels joined. 9. Each payment phase "build" (one-off investment) or "operate" (recurring); build dashed, operate solid; chips "All / Build / Operate" replace flow-type chips in this mode; legend "Build = one-off investment · Operate = recurring payments". 10. No varying thickness. 11. Both modes: selecting a stakeholder fades the rest and labels its arrows; money walkthrough also works in the explorer (current step's payments highlighted). 12. Mobile: if the mobile list doesn't show payments, add "Pays" / "Is paid by" under each stakeholder, grouped by phase. Checks: every payment has a phase, every payment appears in the explorer's money view, poster money badges for new step 4 avoid POSTER_LABELS and boxes (R29). Run all suites against live. Screenshots (live, 1680): explorer Money flows with All, with Build, with operator selected; poster at money step 4." (Ray's message, condensed only where it lists the payments; full text in the session.) | **done, live 2026-10-23** (manual run 39956721403): `d1c7872` (ecosystem-data.v10.js, renamed from v9; ecosystem.html; deploy.yml copies v10; glossary-fi.js comment), tests `1637c0c`. Epoch AI verified 2026-10-23 (14 May 2026): $8.5B a year TCO for 1 GW, servers $5B (60%), energy $0.6B (about 7%, 'the largest OpEx category'), IT equipment over 5 years. Money path 8 steps, 27 payments each with a phase; explorer Money flows mode draws 24 arrows (one per pair and phase), build dashed, operate solid, one width; phase chips and legend line; selection labels arrows in both modes, with a collision pass so labels don't overlap (a long pair shows its first payment and '(+N more)'; tooltip and card list all); the money walkthrough switches the explorer to Money flows and lights each step's payments, the life path switches back; phones list 'Pays' / 'Is paid by' by phase. Texts added beyond Ray's (not user-approved wording, flagged in the report): the equipment -> hyperscaler explanation; the equipment -> operator explanation now says the operator buys the facility's power and electrical equipment (it said compute hardware); life step 6 lists GPU clouds without a second 'and'; the explorer's side-panel hint in Money flows; the mode switch's aria-label. Live: check_ecosystem 212/212 (was 193), check_interactions and layout sweep clean; ecosystem-data.v9.js 404 |
| R77 | 2026-10-23 | "R76 follow-up (next free ID). Your five new texts are approved, except the "(+N more)" case in item 3. Ship and deploy right away without asking unless a text needs changing. 1. No arrow may pass through a stakeholder box other than its own two ends, in both explorer modes. Now hyperscaler → equipment (money) runs straight through Capital & Finance, with its label "servers and GPUs" drawn inside that box; in Relationships mode, equipment → neocloud crosses Capital and Hyperscaler. Route such arrows around the boxes in their way (a curve or a side offset), and keep labels outside boxes. Add a check over all arrows, both modes, with a small margin around each box. Poster, money step 4: the curves to Equipment cross the left edge of the Capital & Finance box. Route them to its left if there's room between it and the printed pills; if not, leave them. 2. Desktop side panel in Money flows mode: when a stakeholder is selected, show "Pays" and "Is paid by", grouped by Build / Operate, first (same content as on phones). Show the relationship cards after it or leave them out in this mode, whichever reads better. 3. Operator → public sector (operate) has four payments, and the label shows the smallest ("land rent... (+3 more)"). Give this pair the label "taxes and land rent"; the tooltip and panel still list all four. Keep "(+N more)" for any other pair. 4. Storage → operator relationship explanation: change it to "Storage suppliers provide the arrays and systems for data protection and backup; like servers, they are bought by whoever runs the IT layer." Run all suites against live. Screenshots (live, 1680), Money flows: All; Hyperscaler selected; Operator selected (panel visible). Also the poster at money step 4." | **done, live 2026-10-23** (manual run 39960088586): `f515319` (ecosystem-data.v11.js, renamed from v10: MONEY_ARROW_LABELS with 'taxes and land rent', the storage explanation; ecosystem.html: every explorer arrow, both modes, is a curve that bends around boxes other than its ends and stays on the map; labels kept off boxes and on the map; the Money flows side panel lists Pays / Is paid by by phase, then the description and examples, no relationship cards), tests `7fe4fa9`. Poster money step 4: the curves to Equipment still cross Capital & Finance's left edge: the gap to the printed pills is about 37px and the euro badge needs about 36px plus its margins, so no clear route; left as Ray allowed (reported by the check, not failed). Queue (found on the way, not in scope): poster money step 2 capital -> construction crosses the Equipment box, step 5 operator -> energy crosses the 'PPA / green energy' pill. Live: check_ecosystem 217/217, check_interactions and layout sweep clean |
| R78 | 2026-10-23 | "R78 – poster crossings + check hardening. 1. Fix all three poster crossings in one pass: Money step 2: capital → construction crosses the Equipment box. Money step 4: both curves to Equipment cross Capital & Finance. Money step 5: operator → energy crosses the "PPA / green energy" pill. For step 4, decouple the € badge from the narrow gap: the curve itself only needs its stroke width plus margin, so place the badge on a segment of the curve where there is room (e.g. near the Equipment end) and route the curve through the ~37 px gap. If that still doesn't work, nudge Capital & Finance or the printed pills by the smallest amount that clears it (≤15 px) without creating new overlaps. Tell me which option you used and why. 2. Harden the crossing check: replace "report instead of fail" with an explicit named allowlist. Every allowed exception must be listed by step/arrow with a one-line reason. Any crossing not on the list fails the check. If all three fixes above succeed, the allowlist should be empty. 3. Remove the stale "requirements unpinned" line from CLAUDE.md (or update it to match reality). Don't change anything else. Run check_ecosystem, check_interactions and the layout sweep against the live site after deploy. Commit, push and trigger the workflow manually right away. Report: commit hashes, run ID, check results, the allowlist contents, and screenshot paths for poster money steps 2, 4 and 5 at 1680." | **2 of 3 crossings fixed, live 2026-10-23** (manual run 39964273800): `37a5c02` (poster: where no badge spot gives a clear curve, the curve is routed first, ends anywhere along the facing box edges, straight or gently bent, shortest clear wins, and the badge goes wherever along it there is room); tests `6032400` (crossing check over all 8 steps against boxes and printed pills, failing on anything outside POSTER_CROSSINGS_ALLOWED and on stale entries); docs `eee38f0` (CLAUDE.md: requirements.txt pinned since R44; resolved queue entry removed). Step 4: both curves to Equipment now run through the ~37px gap left of Capital & Finance, badges on the curve where there's room; no nudge needed. Step 5: operator -> energy runs above the PPA pill. Step 2 not fixed, allowlisted: capital -> construction crosses Equipment & Technology Suppliers, which sits between the two boxes across their full width; the left gap is about 12px after margins and the card column closes the right. Nudging wasn't an option: the boxes and pills are printed in the poster image, so moving overlay coordinates would only misalign the hotspots. Live: check_ecosystem 218/218, check_interactions (hub 59, cards 229, pages 280, layers 98) and layout sweep clean |
| R79 | 2026-10-23 | "R79 – mobile fixes. 1. Chain bar at 360 px: it must not wrap into a broken multi-line layout. Choose the cleanest fix (e.g. a single row with horizontal scroll and a visible scroll cue, or shortened labels at narrow widths) and tell me which you chose and why. 2. Long walkthrough steps on phones: each step's text and controls should be readable without the step overflowing the viewport or pushing the navigation buttons off-screen. Fix it with layout (e.g. a scrollable text area inside the step with fixed nav buttons); don't rewrite the step content. Desktop layouts must not change. Add or extend layout-sweep cases for 360 and 390 px covering both items. Run check_ecosystem, check_interactions and the layout sweep against the live site after deploy. Commit, push and trigger the workflow manually right away. Report: commit hashes, run ID, check results, and screenshot paths at 360 and 390 px for the chain bar and the longest walkthrough step." | **done, live 2026-10-23** (manual run 39969653542): `728fea1` (chain bar, ≤768px: its own full-width row on one line, nowrap with sideways scroll and a fade cue while cut; `!important` beats the strip's inline flex-wrap), `06abbd4` (walkthrough, ≤768px: step text full width in a box capped at 42vh that scrolls, with a fade while cut; Prev and Next share one row under it), tests `a389546` (layout sweep phone cases at 360/390: the live bar and a long three-trend bar, the cue appearing and going; every step of both paths fits the screen with both buttons on one row). Desktop untouched (media-query only). Live: check_ecosystem 218/218 (second run; the first gave no summary, see the queue), check_interactions (hub 59, cards 229, pages 280, layers 98), layout sweep clean incl. the phone cases. At 360 the bar 'Highest score … · Lowest score …' is a few px too wide, so it scrolls with the cue; at 390 it fits |
| R80 | 2026-10-23 | "Check-run stalls (queue item from R79), next free ID. No user-facing change; ship without asking. 1. Every Playwright page load and every suite in check_ecosystem, check_interactions and check_layout_sweep gets an explicit timeout. On timeout, fail with the suite and page name (e.g. "TIMEOUT phones: ecosystem.html load > 30 s"). 2. The summary line always prints, even when a suite aborts or times out, so a run can never end without one. 3. Allowed: one automatic retry of a timed-out page load, logged as "RETRY <suite> <page>" and counted in the summary. A second timeout fails the run. 4. If the retry log shows the same page each time, say which, and whether you see a cause (e.g. the poster image or the data file loading slowly). Report only, no fix. Run all suites against live twice. Close the queue item, log in the ledger, commit, push." | **done 2026-10-23** (tooling only, no deploy needed): `82b6514` adds tools/pw_guard.py: every page load (all 24 in the three tools) gets 30 s with one retry logged as 'RETRY <suite> <page>', a second timeout fails as 'TIMEOUT <suite>: <page> load > 30 s'; other waits 30 s and fail naming the page; a 600 s suite budget checked at each load; a timed-out or crashed suite fails by name and the run goes on; every tool prints its summary in a finally block with the retry and failure counts. Tested against an address that never answers (RETRY, then TIMEOUT phones: ecosystem.html …) and a stuck click (TIMEOUT explorer: ecosystem.html: Locator.click …). Live, twice: check_ecosystem 218/218 both runs, check_interactions hub 59 / cards 229 / pages 280 / layers 98 both runs, layout sweep 11/11 pages and phone cases clean both runs; 0 retries, 0 timeouts in all six. No retry logged, so no page to name from this run; the earlier stalls were mostly on ecosystem.html (R64, R69, R79), which waits for network idle after a 236 KB poster image and a 44 KB data file, but nothing here shows that as the cause |
| R81 | 2026-10-23 | "A RETRY appeared in the checks. In tools/pw_guard.py and the check tools, replace the "networkidle" waits (Playwright discourages them for tests) with wait_until="load" plus an explicit wait for the element each suite needs next (e.g. the explorer SVG, the walkthrough title). Run all suites against live three times; report any RETRY or TIMEOUT. Log in the ledger, commit, push." | **done 2026-10-23** (tooling only): `638c7d5`: pw_guard.load() waits for the load event, then the elements each page's script builds (ecosystem: the poster hotspot, the explorer's operator node, the walkthrough title; hub: the header bar, the layered view's zones and panel title; glossary: the cards; other explainer pages: the header bar; dashboard: the chain bar's content and a card) and the web fonts; error pages skip the element waits; link clicks that open another page wait for that navigation (click_to). All 21 networkidle waits in check_interactions replaced (none left in the three tools). Runs: local once, live three times. 11 of the 12 tool runs had no RETRY or TIMEOUT. Live run 2 of check_interactions: RETRY cards wholesale-colocation.html, whose retry failed with net::ERR_NETWORK_IO_SUSPENDED (this machine's network suspended, not the site; also seen in R69), so TIMEOUT cards (cards 24/25 that run); RETRY pages value-chain.html, recovered. Runs 1 and 3 clean: check_ecosystem 218/218, check_interactions hub 59 / cards 229 / pages 280 / layers 98, layout sweep 11/11 and phone cases |
| R82 | 2026-10-23 | "Keep the computer awake during check runs (next free ID). In tools/pw_guard.py, at the start of each check tool's run call Windows SetThreadExecutionState with ES_CONTINUOUS | ES_SYSTEM_REQUIRED (via ctypes), and reset it with ES_CONTINUOUS alone when the run ends, including on errors (try/finally or atexit). No-op on non-Windows. This prevents idle sleep only, not lid close; say so in a comment. Run the three tools once against live, log in the ledger, commit, push." | **done 2026-10-23** (tooling only): `1f57b79`: pw_guard.keep_awake() sets ES_CONTINUOUS | ES_SYSTEM_REQUIRED at the start of each tool's run and resets ES_CONTINUOUS at exit (atexit, so errors included); no-op off Windows; the comment says it stops idle sleep only, not lid close. Verified the call returns the previous state (set OK). Live once: check_ecosystem 218/218, check_interactions hub 59 / cards 229 / pages 280 / layers 98, layout sweep 11/11 and phone cases; 0 retries, 0 timeouts |
| R83 | 2026-10-25 | "Rename the ecosystem page's view tab "Relationship explorer" to "Interactive map" (next free ID). The explorer now has two modes (Relationships / Money flows), so the tab should name the view, not one mode. Only the visible tab label (and any aria-label or check that asserts the old text); leave code comments as they are. Run check_ecosystem and check_interactions against live after deploy. Commit, push and trigger the workflow manually right away." | **done, live 2026-10-25** (manual run 40194276696): `40588d7`: the ecosystem page's second view tab reads 'Interactive map' (the only visible use of the old label; no aria-label or check asserted it; code comments left as they are). Live: tab text confirmed, check_ecosystem 218/218, check_interactions hub 59 / cards 229 / pages 280 / layers 98; 0 retries, 0 timeouts |
| R84 | 2026-10-27 | "Cross-links and tool URLs: approved now. … Update everything in your list (… DataCenter's chrome.js and render.py, … DataCenter's tools/check_*.py) to https://raydar.fi/, https://datacenter.raydar.fi/ and https://vice.raydar.fi/. … One commit per repo, push … CLAUDE.md and PLAN.md: record the new domains in each repo. Also add this rule to each repo's CLAUDE.md: 'Before a domain or hosting cutover, probe only throwaway paths over http (e.g. /probe-123.html), never / or real pages: GitHub's CDN caches the pre-cutover 404 for an unknown time.'" | **done** `708c16e` (links: business-models/assets/chrome.js, render.py ×2, tools/check_*.py ×3); domains and rule in CLAUDE.md. Live: business-models chrome.js and the render.py links go live at the next deploy (manual workflow_dispatch or the weekday 12:00 UTC run) |
| R85 | 2026-10-28 | "DataCenter '90 days': fix the stale 'Financial data up to 90 days old' line in its CLAUDE.md to '~5 months', matching AI_valuechain. Check whether DataCenter's published pages show the same '90 days' claim. If so, fix that text too, since it's a factual claim on a public page." | **done** `48546da`, live 2026-10-29 (run 116): option (a), Ray 2026-10-29: "R85, option (a): in DataCenter, replace the '90 days' claim (CLAUDE.md and published pages) with 'Quarterly financials are the latest reported quarter and can be several months old'." Applied in render.py (fetch note, legend, footer), fetch_market.py data_age_note and CLAUDE.md. Earlier: '~5 months' was approved 2026-10-28 but held, since DLR's newest usable quarter was 211 days old. reference/ keeps its old text (a copy, not published) |
| R86 | 2026-10-28 | "SyntaxWarnings in DataCenter's render.py (\d at 286, \/ at 463): fix with raw strings or correct escaping. … Confirm the output is byte-identical before and after." | **done** `c0c4216`: the warnings were in tools/check_ecosystem.py (lines 286, 463), not render.py; backslashes escaped, AST identical before and after (all string values byte-identical), no SyntaxWarning |
| R87 | 2026-10-29 | "Spec: align DATACENTER_RAYDAR_SPEC.md:56 with the R85 wording. Own commit." | open |
| R88 | 2026-10-29 | "DataCenter YoY fix: plan now, no code until I approve. It should land before I publish the LinkedIn post that links datacenter.raydar.fi. Reuse AI_valuechain's proven logic: true YoY matched by date (with the 10-day tolerance), EDGAR fill and cross-check, growth_history.json, missing acceleration shown as 'not measured', and no EPS fallback; apply the same honesty fixes the parent got where DataCenter has the same code paths: the live-quote price, the news pooling and keyword purity, and the 'Trend'/'accelerating' labels. List which of these DataCenter actually has; reference/: propose re-syncing it from the current parent or removing it. … before deploy: a before/after replay of sub-layer scores, colours and ratings, plus a dated methodology note on the page ('colour changes on this date reflect the fix, not a market move') and a CHANGELOG entry with the bug's introduction date via git blame; check whether DataCenter's thresholds were tuned on the two-quarter metric, as the parent's were, and whether the capex overlay depends on the growth figures." | **open**: plan approved 2026-10-30 (R89); steps 1–10 in progress |
| R89 | 2026-10-30 | "DataCenter YoY fix: plan approved, steps 1–10 in order, each its own commit, verified before the next. … reference/: remove it (step 8), with the comments changed to 'from the parent at ebc5d6f' and CLAUDE.md's reference section updated. Step 9 calibration: report first. No threshold changes without my approval … The margin-quarter issue: queue it, not in this fix. After deploy: freeze DataCenter's scoring method too (bug fixes only) until a review, for the same comparability reason as the parent. Note it in DataCenter's CLAUDE.md and ledger, with the review alongside the parent's January review. Stop after step 10 and show me the calibration result, the replay columns and the 1680/360 px screenshots before anything deploys." | **open** |

## Queue (this project)

Queued work that isn't a ledger request in progress.

- **gm_delta can describe an older quarter than growth (Ray, 2026-10-30, queued, not in R88).** Margin change comes from yfinance's two newest quarters; once EDGAR supplies a newer quarter (R88 step 1), growth and margin can describe different quarters. Same open issue in the parent's PLAN.md.

- **Run rate never shows (ledger R47).** `run_rate` is null for all 12
  tickers on the live page: `fetch_ticker_data()` fills `revenue_quarterly`
  only on the fallback path (when the quarterly revenue growth can't be
  computed), so the cards' "Run rate $XB/yr" line never appears. Found in the
  R35 check (Known issues, "Scoring inputs").
- **"Kept Green ... isn't confirmed yet" on a steady Green (found 2026-10-20, R59).**
  With history stored, every sub-layer shows the holding note, e.g. "Kept
  Green: latest score 37.3 isn't confirmed yet, and recent sessions were
  mostly Green", although it has been Green in every stored session:
  `_confirmed_color()` has confirmed branches for Red, Orange and Blue but
  none for Green, so a sustained Green always lands in "holding". The note
  is the R36/R42 wording; whether a steady Green should read as confirmed is
  Ray's call (user-facing text).
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

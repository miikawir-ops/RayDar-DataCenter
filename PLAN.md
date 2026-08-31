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

4. **`fetch_market.py`** — swap the parent's `AI_CHAIN_LAYERS` for the 5
   sub-layers + Part B5 ticker universe. Reuse the layer-filtered news
   algorithm exactly (non-negotiable per Part A6). Add a capex-trend fetch
   for the 4 hyperscalers, kept distinct from the existing per-ticker
   `capex_div` field (naming collision risk — different concepts).

5. **`main.py`** — adapt aggregation from 7 layers to 5 sub-layers. Reuse
   market-cap weighting, bottleneck leader boost, 3-day confirmation as-is.
   Apply decisions #2 and #3 for single-ticker sub-layers. Add the capex
   direction classification (accelerating/stable/decelerating) and the
   static beneficiary map (Part B3), consumed by render, not by
   score_engine.

6. **`render.py`** — adapt layer cards to the 5 sub-layers. Add the
   top-level capex-direction strip and per-sub-layer beneficiary badge as
   a display-only addition (decision #1). Keep the dark hero/visual system
   as-is for family consistency (Part A5).

7. **Deploy plumbing** — `index.html` at repo root (required for GitHub
   Pages bare-URL resolution, per CLAUDE.md), GitHub Actions workflow,
   `publish.py` adapted from `reference/`. Remote not created yet — local
   repo only until there's something to deploy.

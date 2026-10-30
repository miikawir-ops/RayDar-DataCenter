# Changelog

## Deploy date added on deploy — revenue growth was not year-over-year; news pooled across sub-layers (ledger R88)

**Methodology change.** Scores from the deploy date on are not like-for-like with earlier ones. `config.MODEL_VERSION` goes from 2 to 3. Entries stored under version 2 are kept exactly as published. The first version-3 entry carries `methodology_change: true`. Colour confirmation ignores entries from other versions, the page compares nothing across the change ("no comparison: method changed"), the heat trail marks the last old-version day, and a dated note on the page says colour changes reflect the fix, not a market move. Backtests must not compare across it.

### What was wrong

All of these came in when the parent's code was ported, between 2026-09-15 and 2026-09-18, and were live from the first deploy (2026-09-20) until this fix: about six weeks.

- **Revenue "YoY" growth compared the latest quarter with the one 2 quarters back.** `fetch_market.py` took the `dropna()` columns 0 and 2 as "this quarter vs a year ago", and 1 and 3 as the previous quarter's version. So acceleration (the growth delta, 65% of the score through the acceleration signal) was the difference of two 2-quarter changes. When a column was missing, `growth_prev` fell back to `info["earningsGrowth"]`, which is EPS growth, not revenue. Introduced in `a862f7e` (2026-09-15), the port of the parent's fetch code; the parent had the same bug and fixed it on 2026-10-24.
- **News velocity was pooled across a sub-layer.** `run_pipeline()` passed the whole sub-layer's ticker list into the news ownership filter, so every company in a sub-layer got the same score. On 2026-10-29's live headlines that was 7.0 for all four optical companies, against 3.0 / 0.0 / 3.0 / 1.0 each on its own feed. Introduced in `a862f7e` (2026-09-15).
- **The sub-layer's news number came from the first company in config order**, and the divergence text paired it with the best company's growth delta: two companies' signals in one sentence. Introduced in `252ebbd` (2026-09-18).
- **Unmeasured acceleration was treated as accelerating.** With the growth delta unknown, the +8% high-margin bonus still applied, a company above 65 could be Red, and a sub-layer could reach Red with no measured company. Introduced in `8110074` (2026-09-17), and for sub-layers in `1c63eb1` (2026-09-17), the port of the aggregation.
- **Labels.** The layer card's "Momentum" was revenue acceleration, not price. A missing delta read "unknown". Introduced in `252ebbd` (2026-09-18).

### Fix

- Growth is date-matched YoY: each quarter against the one ending 350–380 days earlier. Acceleration is the change in that YoY between the latest two quarters, so it needs 6 quarters. yfinance has 5–6, so `edgar.py` (unchanged from the parent) reads SEC XBRL companyfacts. A revenue concept is used only if it matches yfinance within 1% on every overlapping quarter. EDGAR also supplies newer quarters yfinance leaves blank. No EPS fallback. The workflow passes `secrets.SEC_USER_AGENT`.
- YoY is persisted per quarter-end in `growth_history.json` on the data branch, as a fallback and cross-check.
- Unmeasured acceleration gets no margin bonus and never reaches Red, for a company or a sub-layer.
- Each company's news is scored on its own feed; the sub-layer's news number is the best company's own.
- "Rev. acceleration" replaces "Momentum" on the layer card. The expanded card gives the YoY change in pp, or "not measured".
- `reference/`, the 2026-08-31 copy of the parent's code with all of these bugs, is removed.

### Verified

- Each fix has a check in `tools/` that fails on the old code: `check_revenue_growth.py`, `check_acceleration.py`, `check_news.py`, `check_method_change.py`. `check_confirmation.py` still passes.
- Replay, calibration and live check: *added before deploy.*

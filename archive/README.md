# Archive: recovered dashboard history (never read by the pipeline)

Nothing in this folder is read by `main.py`, `render.py` or the deploy
workflow. It is kept because GitHub keeps Actions logs for 90 days, and until
2026-10 the dashboard never persisted its history in CI (PLAN.md ledger R28):
these logs are the only record of what it computed.

- `run_logs/raw/<run id>.zip`: the raw Actions logs of every run listed on
  2026-10-10 (79 runs from 2026-09-20; zips of a few bytes are runs GitHub
  kept no log for, e.g. the cancelled 2026-10-05 scheduled run).
- `run_logs/runs.json`: the API's run listing at that time (ids, events,
  times, commits, conclusions).
- `run_logs/per_run_sublayer_scores.json`: each run's per-sub-layer weighted
  score and colour as logged by `main.py`, with the log time of scoring.
- `rebuilt_sublayer_history_2026-09-20_to_2026-10-09.json`: 15 days, one per
  UTC date, from the last run of that date that logged scores.

Caveats, so nobody reads more into these than they hold:
- Per-sub-layer weighted score, colour, best ticker and its score only. Not
  logged: per-ticker acceleration / constraints / smart money, other tickers'
  scores, fund_delta, ratings.
- Colours are raw single-day colours (confirmation never ran).
- Dated by UTC wall clock, not by US market session. 13 of the 15 days come
  from runs during US trading hours (13:30-20:00 UTC on weekdays), when the
  latest daily bar may be unfinished; 2026-10-09 is after the close;
  2026-09-20 is a Sunday run, i.e. Friday 2026-09-18's data.
- Several runs on one date can differ by up to 3.5 points per sub-layer.

# data branch: RayDar Data Center pipeline state

Holds the dashboard's persisted state, written by the deploy workflow's
save-history job (PLAN.md ledger R33a, R59):

- `scores_history.json`: one entry per US market session (the last run for a
  session replaces earlier ones), read back for multi-session colour
  confirmation, the score delta and the heat trail.
- `audit_log.json`: one entry per ticker per session, no cap: score, the
  acceleration / constraints / smart-money sub-scores, fund_delta, missing
  fields and model_version.

Every run restores both files from here before the pipeline and fails if
either is missing or unreadable; it never starts a fresh history silently.
Both started empty on 2026-10-15 (no history was seeded from recovered logs).

`archive/` is historical material the pipeline never reads. Don't edit by
hand except to recover from a failure, and record any such edit in PLAN.md.

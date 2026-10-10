# data branch: RayDar Data Center pipeline state

Holds the dashboard's persisted state, written by the deploy workflow's
persist job (PLAN.md ledger R33): `scores_history.json` and `audit_log.json`
at the root, once persistence is live. `archive/` is historical material the
pipeline never reads. Don't edit by hand except to recover from a failure,
and record any such edit in PLAN.md.

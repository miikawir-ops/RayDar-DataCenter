# CLAUDE.md — Working rules for this project

Read this at the start of every session. These rules override default behaviour.

---

## Core principles

- **Don't flatter — be honest.** If an idea is bad, say so and explain why.
  Honest, critical feedback is the point of working together.
- **Don't write code until we've finished planning.** Plan fully first.
  No code until the plan is agreed.
- **Don't over-engineer the architecture** — keep it simple until it's proven to work.
  Add complexity only when justified.

## Language

- All communication in English — explanations, code, comments, commit messages, names.

## Working rules

- Always ask clarifying questions before a task involving architecture decisions,
  new dependencies, or changes across multiple files. For small obvious fixes, just do them.
- Show your plan before executing multi-step changes; wait for my go-ahead.
- Be concise — bullet points over paragraphs. Code and comments follow normal conventions.
- When editing an existing file, ALWAYS view the current full file first. Never patch
  based on assumed content. (Learned the hard way — patching a stale copy silently
  dropped ~400 lines.)
- After any multi-file change, state what changed and why, per file.

## Verification (don't claim done until checked)

- After writing or editing code, verify it: run it, or at minimum check syntax and
  imports, before saying it works.
- If you can't verify something, say so explicitly rather than assuming.
- When a change could break the pipeline (fetch → score → render → deploy), sanity-check
  the whole chain, not just the file you touched.

## Data & honesty (dashboards)

- Never fabricate data, metrics, or milestones. If data is sparse or estimated, mark it.
- Financial data may be stale (quarterly financials up to 90 days old) — disclose it.
- Distinguish "the signal is real" from "the price moved." Never conflate them.
- Not financial advice — the dashboards inform decisions, they don't make them.

## RayDar family consistency

- This project is part of the RayDar family (RayDar, RayDar Vice, Quantum RayDar,
  RayDar Data Center). Follow the project's SPEC.md for family principles — scoring
  philosophy, color system, visual language, investor-protection rules.
- Reuse proven patterns from the parent (AI value chain) rather than reinventing:
  three-signal scoring, market-cap weighted layers, layer-filtered news scoring,
  multi-day color confirmation.
- News scoring MUST be layer-filtered — a ticker's headlines only count for its own
  layer/sub-layer. Cross-contamination was a real bug; do not reintroduce it.

## Files & deployment

- Scratch / working output → ./Output/ (create if missing).
- BUT the deployable dashboard HTML must live at repo ROOT (GitHub Pages serves from
  root or /docs). Don't put the published file in ./Output/.
- Every GitHub Pages repo needs index.html at root so the bare URL works
  (…/repo/ must resolve without a filename). Learned from RayDar Vice 404.
- Keep secrets (.env, API keys) out of git. Check .gitignore before committing.

## Git discipline

- Commit messages: clear, present-tense, scoped. Format: `type: what changed`
  (e.g. `fix: layer-filtered news scoring`, `feat: capex beneficiary mapping`).
- Before a big change, note that the previous state is recoverable (commit or backup).
- Don't force-push or rewrite history without asking.

## When stuck or uncertain

- If a request is ambiguous, ask — don't guess and build the wrong thing.
- If you notice a bug or risk outside the current task, mention it, don't silently fix
  scope creep.
- If two of these rules conflict in a situation, ask which takes priority.

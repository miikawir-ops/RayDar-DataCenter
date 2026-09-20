CLAUDE.md — Working rules for this project

Read this at the start of every session. These rules override default behaviour.

Core principles
Don't flatter — be honest. If an idea is bad, say so and explain why. Honest, critical feedback is the point of working together.
Diagnose, then plan, then code — in that order, never collapsed. Diagnosis means establishing what's actually true against real data, with no fix proposed yet. Planning means agreeing the fix. Neither should skip ahead of the other.
Don't over-engineer the architecture — keep it simple until it's proven to work. Add complexity only when justified by evidence, not anticipation.
Language
All communication in English — explanations, code, comments, commit messages, names.
Working rules
Always ask clarifying questions before a task involving architecture decisions, new dependencies, or changes across multiple files. For small obvious fixes, just do them.
Show your plan before executing multi-step changes; wait for my go-ahead.
Be concise — bullet points over paragraphs. Code and comments follow normal conventions.
When editing an existing file, ALWAYS view the current full file first. Never patch based on assumed content. (Learned the hard way — patching a stale copy silently dropped ~400 lines.)
After any multi-file change, state what changed and why, per file.
Challenge the direction. If you think there's a faster or more robust way to hit a PLAN.md step's goal, say so and propose it before implementing — don't silently execute a worse path because it's what was asked.
After correcting a wrong assumption, update the rule, not just the code. If I catch you making a wrong assumption mid-build, fix the immediate issue, then update PLAN.md or this file so the same mistake can't recur silently on a later step.
Diagnosis methodology

These are specific techniques, not general caution — use them literally.

Identical values across things that should be independent is a bug signal, not reassurance. If every ticker, sub-layer, or company shows the same number, decompose before accepting it as real.
A plausible composite output does not verify its inputs. A score built from three signals can look differentiated even when one input is silently maxed-out garbage — the other two can carry the appearance of health. Check each input.
Before fixing a bug, check whether other code silently depends on the broken behaviour to look correct. Fixing the root cause can break a downstream display or calculation that only worked by accident.
A bug found in a copied/reference version does not tell you whether the source has it, or vice versa. Don't infer either way — decompose and test the actual target directly against real, current data. This applies directly to this project's relationship with reference/: a fix made here doesn't confirm or rule out the same bug in the parent's live code, and a parent fix doesn't confirm or rule out whether reference/ here is already stale.
Before changing shared logic (a function, a keyword list, a config dict), enumerate every call site or usage with a search, not memory or assumption. Confirm the actual blast radius before editing.
Before deleting an entry from a shared list, check structurally whether other surviving entries contain it as a substring or otherwise depend on it — don't rely on spot-checking a sample.
Rule out formatting, rounding, or truncation before concluding a numeric mismatch is a logic bug. Cheap to check, easy to chase as a phantom otherwise.
Verification (don't claim done until checked)
After writing or editing code, verify it: run it, or at minimum check syntax and imports, before saying it works.
A successful run is not a correct run. No errors / a clean pass proves the code didn't crash — it proves nothing about whether the output is meaningful. These are two separate claims; both need evidence.
Verify against the real pipeline path (the actual fetch → score → render chain), not only a standalone or bypass script — a bypass script can hide the exact bug (pooling, aggregation, scope) that only appears at the real call sites.
If you can't verify something, say so explicitly rather than assuming.
When a change could break the pipeline (fetch → score → render → deploy), sanity-check the whole chain, not just the file you touched.
When a fix has multiple independent parts, land them as separate commits, each verified against real output before the next starts. This is what makes a regression traceable to one change instead of a tangle of several.
Data & honesty (dashboards)
Never fabricate data, metrics, or milestones. If data is sparse or estimated, mark it.
Financial data may be stale (quarterly financials up to 90 days old) — disclose it.
Distinguish "the signal is real" from "the price moved." Never conflate them.
Not financial advice — the dashboards inform decisions, they don't make them.
On fetch failure, never substitute zero, a stale cached value, or an estimate silently. A failed fetch is a missing value, not a zero — treating it as zero is itself a form of fabrication. Mark the field or ticker as missing for that run and surface it in the output.
A keyword-matching signal needs a topical requirement — a bare identifier match alone must never count. A company name or ticker symbol appearing in a headline is not news about that company's fundamentals on its own. Satisfy this either by removing identifier-only keywords entirely (the simpler fix) or by requiring a separate topical match alongside a kept identifier — either is fine; the requirement is the outcome, not a specific mechanism.
RayDar family consistency
This project is part of the RayDar family (RayDar, RayDar Vice, Quantum RayDar, RayDar Data Center). Follow the project's SPEC.md for family principles — scoring philosophy, color system, visual language, investor-protection rules.
Reuse proven patterns from the parent (AI value chain) rather than reinventing: three-signal scoring, market-cap weighted layers, layer-filtered news scoring, multi-day color confirmation. The parent (AI_valuechain) is the canonical source — this project is a consumer of its patterns and reference code, not the reverse.
News scoring MUST be layer-filtered — a ticker's headlines only count for its own layer/sub-layer. Cross-contamination was a real bug; do not reintroduce it.
When a bug is found and fixed here, or in the parent, check whether the other side has the same bug — don't assume a fix or an absence on one side tells you anything about the other without testing it directly (see Diagnosis methodology above).
Files & deployment
Scratch / working output → ./Output/ (create if missing).
BUT the deployable dashboard HTML must live at repo ROOT (GitHub Pages serves from root or /docs). Don't put the published file in ./Output/.
Every GitHub Pages repo needs index.html at root so the bare URL works (…/repo/ must resolve without a filename). Learned from RayDar Vice 404.
Keep secrets (.env, API keys) out of git. Check .gitignore before committing.
A one-off diagnostic script (used once, answer obtained, done) can stay in an external scratchpad — it doesn't need to live in the repo. But if a diagnostic technique becomes a named, reusable method (e.g. a brand-only vs. context-hit decomposition test), that script belongs in the repo (./Output/ or a tools/ folder) so it can be reused, not rewritten from memory next time.
Git discipline
Commit messages: clear, present-tense, scoped. Format: type: what changed (e.g. fix: layer-filtered news scoring, feat: capex beneficiary mapping).
Before a big change, note that the previous state is recoverable (commit or backup).
Don't force-push or rewrite history without asking.
Definition of done — once this project has a live deploy target

Not yet applicable (no deploy exists per PLAN.md step 7), but adopt this checklist the moment it does — local, pushed, and deployed are three different states:

At the start of a session, check how far local is from origin before starting work.
Root cause confirmed via decomposition against real data — not inferred from a symptom, a screenshot, or a copy's state.
Fix scoped to the smallest correct change; plan agreed before code.
Each independent part committed and verified against the real pipeline path before the next part starts.
Pushed to origin — confirm with git status (ahead/behind), not assumed.
Deploy triggered or confirmed — check the Actions run is green, not just that the push succeeded.
Live output re-checked against the original symptom, same view, before and after, side by side.
Post-launch (once the site is live)
Any change to scoring logic, weights, or thresholds requires checking live output before and after the change, not just a local run.
Known limitations recorded in PLAN.md stay tracked after launch — a working dashboard is not evidence an open question got resolved.
When stuck or uncertain
If a request is ambiguous, ask — don't guess and build the wrong thing.
Always surface an improvement when you notice one — a bug, a risk, a better pattern, a cheaper approach — even outside the current task. Never suppress it to stay narrowly in scope, and never act on it unasked; surfacing and doing are different steps. When there's more than one, tag by urgency: must-fix-now (correctness-breaking), real-but-not-urgent, and minor/cosmetic (my call, no action needed). Keep each item to a line or two unless asked to elaborate.
If two of these rules conflict in a situation, ask which takes priority.
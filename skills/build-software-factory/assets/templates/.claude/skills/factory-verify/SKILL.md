---
name: factory-verify
description: Perform revision-bound pre-merge application verification and prepare post-release evidence handoffs.
---

# Verify

Resolve the factory root as `../../../` relative to this file's containing folder. Follow repository instructions and policy.md; no new authority is granted.

Inspect the final diff, acceptance.md, research.md, verification.md and configured operations. Reuse the stack's existing CI/test setup. For checks still required, run authorized G1 production-equivalent local smoke over a critical success and expected-failure path, plus G2 change-targeted tests selected for this diff. Build/lint/hash success alone is insufficient. Greenfield first gets a concrete fixture/assertion/test implementation design, never invented commands or invented passing results.

Record Every still-required pre-merge check, defaulting to G1/G2 and A/R checks, for the actual revision with command/manual procedure, environment, target, observation time, exit status and evidence. NOT RUN, BLOCKED, FAILED, missing or stale evidence blocks pre-merge readiness. Run the builder's gates.py --factory <root> --stage pre-merge --revision <actual-revision> when available; it validates records only and runs no checks. Required reviews must cover this final diff. Preserve visual-fidelity requirements where applicable.

## Post-action and video handoff
When video work is enabled/requested and has not been waived, prepare a script-first shot list for the single change using done-video-recipe.md when present or the installed builder recipe. Plan genuine app/backend interactions, fixture disclosures, concise composition/callouts, branding, captions and actual playback QA. Remotion is optional. V2 preview cannot replace the post-action V1 subject. Record chosen voice/tool/delivery and missing authority; obtain approval immediately before narration unless explicitly requested in the current prompt. No media generation, upload or message is implied by preparing this handoff.

Verify owns current pre-merge observations in verification.md; task owners update task-plan.json atomically using status.py within scope. Store durable logs/artifacts in reviewed project evidence storage outside this factory and record stable references/access owner; a temporary worker transcript is insufficient retention. The gate Revision is the exact tested subject, while a later evidence-only storage commit is a distinct identity recorded in handoff metadata. Do not relabel old checks to the storage SHA. Review any evidence-only diff; if it changes the tested subject or triggers a new deployment, obtain separate verification for that actual subject. No CI enforcement is enabled automatically.

Identify required post-merge A/R checks and G3's actual web/artifact target. Future post-action evidence does not block pre-action readiness. If done_videos.enabled is true, put the scoped narrated-demo plan, owner, permitted synthetic data, recording/storage/publication boundaries and G3 prerequisite in release-handoff.md. Do not record the shipped demo before the action or claim a planned artifact exists. Release owns G3 then V1; blocked tooling or authority must be reported explicitly.

## Exit gate
When a task-fitted secret/connection-string check is relevant, use
connection-string-review.md when present or the installed builder's guide. Review
candidate provenance and synthetic positive/negative fixtures; localhost, fixture
usernames and documentation paths are not exemptions. Keep suspected values out of
logs. A revised check needs reviewed contract changes and fresh exact-subject
evidence; preserve previous failures and deliberate WAIVED status.

Review promised failure properties beyond happy paths. When the actual task uses caller IDs/durable persistence, inspect allowed special-key/collision behavior, save/load plus fresh-process retries, removal semantics, multibyte/short/zero/failed writes and committed-state preservation using disposable fault fixtures. Fit checks to the language/storage API and seek independent review when risk warrants; do not impose this matrix on unrelated work. A kill-before-commit smoke alone proves no complete-write guarantee.

If independent review finds a defect after a green suite, preserve the reproducer/failing subject and record actual FAILED/BLOCKED results (or an explicit WAIVED row with its recorded failure). Repair on a new exact subject, review the final diff and rerun relevant required checks before restoring readiness. Retain prior failures as history; never relabel old evidence to the repaired SHA or claim PASS from counts alone.

Carry unresolved structured assumption labels/provenance/blockers into the diagnostic handoff for owner review. A confirmed label is not independently verified evidence; free-text sources do not authorize actions. Keep decision status and user-chosen gate waivers explicit rather than creating hidden automatic gates.

Return a ready recommendation only when all still-required pre-merge checks and reviews pass, reporting explicit optional checks as WAIVED. A blocked diagnostic handoff is always useful and must retain its BLOCKED status. Never merge or deploy as a verification side effect.

## Deliberate optional checks
Respect an explicit Required=no/false in a living verification row without requesting another approval. Keep the expected row present; report it as WAIVED with its recorded result (including failures), not tests-passed. Missing/malformed/duplicate rows are errors. Only still-required checks block readiness. Optional tests do not authorize merge, deployment, recording or publication.

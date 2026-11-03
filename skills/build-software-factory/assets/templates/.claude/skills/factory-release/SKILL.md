---
name: factory-release
description: Prepare a truthful readiness handoff, perform only authorized release actions, and confirm actual targets.
---

# Release

## Pre-action
1. Prepare release-handoff.md, blocked or not, preserving evidence for diagnosis. Mark it READY FOR AUTHORIZED ACTION only when every still-required pre-merge check passes for the exact reviewed revision and required reviewer verdicts cover that revision. Run `gates.py --factory <root> --stage pre-merge --revision <rev>`.
2. Before first provisioning, verify framework, runtime, build and output settings against the project and current official provider guidance. Discover the live plan/SKU identifiers and record the selection, limits, cost, source and time; never guess from a sample, and a free plan is not permission. Inventory permitted environment names (no values) and who manages each target; required names and integration-managed extras need project-specific checks, since the generic gates enforce no env allowlist.
3. Without publication authority, deliver the prepared handoff and stop.

## Coordinate one release lane

For each subject and actual target, identify one release owner and the authorized
coordination mechanism before migration, G3 or V1 work starts. Separate triggers
must not each infer ownership from a label, row or local file. If two owners might
act, require a separately authorized, tested atomic admission mechanism at their
shared coordination boundary; otherwise stop and resolve ownership with the owner.
A non-owner waits and consumes the owner's revision-bound outcome and durable
evidence; it does not rerun migration, smoke or narration. Transfer ownership only
through the agreed procedure after the prior owner stops or its outcome is resolved.
No mechanism is installed or authority granted by this guidance.

Before traffic can reach code that requires a schema change, establish an authorized
migration-before-promotion sequence or a verified compatible expand/contract plan
for the actual deployment platform. Check pending migrations and compatibility in
the project-specific release plan, with named owner, backup and rollback decisions.
If automatic promotion can expose incompatible code first, a later G3 observation
cannot prevent that exposure: block the release handoff and escalate the ordering
problem. Do not run migrations or change promotion settings without scoped authority.

If an authorized project uses Neon and Drizzle and proposes a different migration
transport, inspect the project's actual driver, migration implementation and current
provider documentation first. Neon HTTP supports single queries and non-interactive
transactions; session or interactive transactions need a different supported path
([Neon](https://neon.com/docs/connect/choose-connection),
[Drizzle](https://orm.drizzle.team/docs/connect-neon)). Verify migration ledger,
transaction atomicity, locking, retries and rollback against a disposable environment
before recommending a project-specific recipe. A connectivity failure does not
authorize a network-policy bypass, credential disclosure, installation or migration.
No generic transport fallback is activated by this skill.

## Post-action
4. Only after a separately authorized merge, deploy, install or publish: run G3, if still required, against the actual target and merged revision — the real URL for web targets, the installed or published artifact for everything else — plus required post-action A/R checks. Record result, target, revision, command or observation, time, exit status and evidence, then run `gates.py --factory <root> --stage post-merge --revision <merged-rev> --target <target>`. An optional G3 is reported WAIVED.

For multi-actor checks, use Build's scenario and actor prerequisites to confirm the approved actors exist with the needed roles on this target before execution. If they are unavailable, do not create users, seed production or insert rows to make G3 pass without separately scoped authorization. Preview or disposable-environment evidence remains evidence for that named environment, even when the revision matches production.

Account for each scenario excluded by a tag, guard or filter, including its requirement, actual result and reason, in verification.md and release-handoff.md. Use the existing gate rows: a missing required scenario stays BLOCKED/NOT RUN in G3, or in a named additional required post-merge row when the project explicitly separates its scope. G3 must describe its actual checked scope and link any separated scenarios; a passing filtered command does not establish a pass for the omitted flow. For an explicitly optional scenario, retain its actual result in an optional row (`Required? no`) and record the user's choice and rationale; assessment reports WAIVED. Do not put WAIVED in the Result column or silently make a required scenario optional. Report release completion WITH WAIVERS when applicable. The gate helper validates recorded rows, not which scenarios a test filter omitted, so reconcile the collected/executed scenarios with the planned scope before recording a pass.

Keep raw filter expressions and command logs in a non-secret evidence artifact and put a table-safe reference in the gate row. The living-record writer rejects literal pipe characters in observation fields; backslash-escaping a pipe does not make it valid in this table. An evidence-format error is not a reason to omit the excluded scenario.

5. If a required post-action check fails or cannot run, report UNCONFIRMED/FAILED at once to the release owner with evidence, target, revision and the diagnosis or rollback decision needed. Roll back only within existing authority. An unknown target stays blocked; only accepted no-release scope records G3 NOT APPLICABLE with rationale.
6. Record the deployed subject SHA separately from any evidence-storage commit. If storing evidence redeploys, identify and separately confirm the newly deployed revision. A CI adapter's green pre-merge assessment is not deployment confirmation.

## Video (when enabled)
7. Read done_videos triggers in config: omitted means release-only V1; post_g3_release selects V1 here. If G3 is required it passes first; if optional, record its waiver. If V1 is required, record the authorized demo with shipped revision, target, artifact and time, following done-video-recipe.md: genuine target footage, scripted story, captions, provenance, watched and listened-to output, delivery only on an approved channel. Approval comes immediately before narration unless the current prompt asked for it. A script, silent draft or render is not a delivered demo; a blocked required demo stays blocked; V2 never substitutes.

## Exit
A truthful prepared handoff, or an authorized action confirmed by all still-required post-action checks (optional ones COMPLETED WITH WAIVERS), with unresolved assumption blockers and the next owner named. Report code readiness separately from an incomplete review package.

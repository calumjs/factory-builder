---
name: factory-verify
description: Perform revision-bound pre-merge application verification and prepare post-release evidence handoffs.
---

# Verify

## Run the pre-merge checks
1. Inspect the final diff against acceptance.md, research.md, verification.md and the configured operations. Reuse the project's existing CI and test setup.
2. For each still-required check, run the authorized G1 production-equivalent smoke over a critical success path and an expected-failure path, plus the G2 change-targeted tests for this diff. Greenfield gets a concrete fixture, assertion and test implementation design first.
3. For configured smoke recipes, run the canonical argv in the configured environment against the matching target; the gate checker compares records only. A changed recipe needs a reviewed synchronized update and fresh observations.
4. Review promised failure properties beyond the happy path. Where the task uses caller IDs or durable persistence, exercise special-key and collision behaviour, save/load with fresh-process retries, removal semantics, and multibyte, short, zero and failed writes with disposable fault fixtures; seek independent review when risk warrants. A kill-before-commit smoke proves no complete-write guarantee.
5. When a task-fitted secret or connection-string check applies, use connection-string-review.md: review candidate provenance with synthetic positive and negative fixtures. Localhost, fixture usernames and documentation paths are not exemptions. A revised check needs a reviewed contract change and fresh evidence.

## Reconcile mapped tests with actual runs
For each test required for this change, identify the applicable mapped test or suite; classify fixture or helper paths and separately run suites rather than assuming every mapped path is a runnable spec. Against the **same subject revision**, runner configuration, project(s), filters and intended shards used by the actual job, compare the runner's collection/list output with the required runnable tests and retain the collection and final result evidence. Use the stack's supported collection mechanism after inspecting the existing setup; do not run untrusted configuration merely to validate a map.

- A required spec excluded by configuration or filters, or zero required tests collected, is NOT RUN/BLOCKED for that coverage; investigate and rerun the appropriate authorized job before claiming coverage. Do not silently broaden test selection or claim success from a map or collection listing.
- Reconcile per-test final results with the collected tests: a skipped, interrupted, failed or missing required result is not a pass. Record the actual scope and passed, failed, skipped, not-run and retry/flaky counts; a required check must pass or be deliberately waived as WAIVED.
- For sharded execution, check the intended shard set and aggregate distinct results for the same subject and configuration. A missing or failed shard leaves its required tests unverified; do not sum retries as independent tests or infer a pass from another shard. Separate suites need their own job evidence.

Example evidence interpretations: mapped spec excluded by a project filter: NOT RUN; a valid collection with zero tests: NOT RUN; collected test skipped: SKIPPED, not passed; one of two expected shards absent: incomplete. A listed test that actually passes in the matching run can support its own coverage only; it does not prove other mapped tests ran.

## Record
6. Record every still-required pre-merge check (G1, G2, A/R rows) in verification.md for the exact revision: command or manual procedure, environment, target, observation time, exit status, evidence reference. Task owners update task-plan.json with status.py. Preserve visual-fidelity requirements where applicable.
7. Run the builder's `gates.py --factory <root> --stage pre-merge --revision <revision>`; it validates records and runs nothing.
8. If independent review finds a defect after a green suite, keep the reproducer, record FAILED or BLOCKED (or WAIVED with the failure for an optional row), repair on a new subject, review the final diff and rerun the relevant checks before restoring readiness.
9. An authorized CI adapter (ci/README.md) assesses records at storage E against explicit tested S chosen from the real test job, never by finding a passing row.

## Hand off
10. Identify required post-merge A/R checks and G3's actual target; they do not block pre-action readiness. Put the scoped V1 plan, owner, permitted data and boundaries in release-handoff.md when a release trigger is enabled.
11. When video is enabled and not waived: plan V2 only for pre_merge_preview and V1 only for post_g3_release, with separate subjects. Prepare a script-first shot list from done-video-recipe.md with genuine app interactions, fixture disclosures, composition, branding, captions and playback QA (Remotion optional). Record the chosen voice, tool and delivery; approval comes immediately before narration unless the current prompt already asked for it.
12. Carry unresolved assumption labels, provenance and blockers into the handoff.

## Exit
When using the installed incremental-workflow.md, report explicitly selected scope and excluded rows. Scoped eligibility is not whole-project readiness or release authority; obtain fresh evidence for a new subject.

A ready recommendation only when all still-required pre-merge checks and reviews pass for this revision, optional checks reported WAIVED; otherwise a BLOCKED diagnostic handoff. Verification never merges or deploys.

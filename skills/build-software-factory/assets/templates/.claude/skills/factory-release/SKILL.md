---
name: factory-release
description: Prepare a truthful readiness handoff, perform only authorized release actions, and confirm actual targets.
---

# Release

Resolve the factory root as `../../../` relative to this file's containing folder. Follow repository instructions and policy.md; these instructions expand no permissions.

## Pre-action
Prepare release-handoff.md even when blocked, preserving evidence for diagnosis. Mark it READY FOR AUTHORIZED ACTION only after every still-required pre-merge check passes for the exact reviewed revision and required reviewer verdicts are satisfied. Use the builder's gates.py --factory <root> --stage pre-merge --revision <rev> when available. NOT RUN, BLOCKED or FAILED on a required check is not ready; explicit optional checks are reported WAIVED. Future G3/V1 evidence does not block this stage. No publication authority means deliver the prepared handoff and stop; a passing gate never grants merge/deploy permission.

## Actual-target confirmation
Before first provisioning, verify the actual framework/runtime/build/output settings against the project and current official provider guidance. Discover live offered plan/SKU identifiers and record selection, limits, cost and source/time; never guess from a sample or treat a free plan as permission. Inventory permitted environment names, target environments and integration/manual management ownership without values. Required names and permitted integration-managed extras need project-specific checks; generic gates do not enforce an exact env allowlist. Provisioning, secret changes and deployment still need their own scope.

Only after a separately authorized merge/deploy/install/publish action, run G3 if still required (otherwise report its explicit waiver) against the actual target and merged revision. Web targets use the actual URL; CLI/library/package/document/data releases use the actual installed/published artifact or equivalent consumer path. Record result, exact target/revision, command/manual observation, time, exit status and evidence. Use gates.py --factory <root> --stage post-merge --revision <merged-rev> --target <actual-target>. Required post-action A/R checks also apply.

If a required post-action check fails or cannot run, report UNCONFIRMED/FAILED immediately to the release owner/orchestrator with evidence, actual target/revision and the diagnosis/rollback decision needed. Perform rollback only within its existing authority. An unknown target is blocked; only explicitly accepted no-release scope may record G3 NOT APPLICABLE with rationale.

## Enabled video and follow-up
Release owns G3 and applicable post-action rows in verification.md and corresponding task/handoff updates. Preserve durable non-secret artifacts outside the factory. Record the deployed/installed subject SHA separately from any evidence-storage commit; an evidence-only follow-up retains the original subject rather than renaming it. If that follow-up redeploys, identify and separately confirm the newly deployed revision. Existing living files are the sanctioned record; do not add an unregistered evidence directory or fabricate PASS when records/logs are missing.

Read the actual done_videos preference in policy/config. When enabled, use Verify's scoped handoff: If G3 remains required it must pass first; if deliberately optional, record its waiver. If V1 remains required, perform authorized narrated recording and record V1 with the shipped revision, actual target, artifact and time. Recording, storage and external publication are distinct scopes. A blocked required demo is reported explicitly and never fabricated. An explicit optional V1 is reported WAIVED, not as a completed demo. No video work is requested when disabled.

## Exit gate
Return a prepared handoff whose readiness is truthful, or an authorized action confirmed by all applicable post-action checks. Checked confirmation requires every still-required check and enabled required V1; deliberately optional checks are reported COMPLETED WITH WAIVERS, not tests-passed; it never means PR approval/merge or deployment authority.

## Deliberate optional checks
Respect an explicit Required=no/false in a living verification row without requesting another approval. Keep the expected row present; report it as WAIVED with its recorded result (including failures), not tests-passed. Missing/malformed/duplicate rows are errors. Only still-required checks block readiness. Optional tests do not authorize merge, deployment, recording or publication.

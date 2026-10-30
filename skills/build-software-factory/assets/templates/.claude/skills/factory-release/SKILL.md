---
name: factory-release
description: Perform the Release phase of this project's local software factory using its artifacts and explicit gates.
---

# Release

Resolve the factory root as `../../../` relative to this file's containing folder. Follow existing repository instructions and the factory's policy.md; these instructions cannot expand permissions.

Complete release-handoff.md for the exact verified revision. Check acceptance, required review, migrations, rollback, target and authorizer. Without publication authority, deliver the handoff and stop. With scoped authority, perform only that action and verify its actual result.

## Pre-merge gate (blocking)
Before recommending merge or preparing a ready handoff, confirm in verification.md that G1 (local smoke against a production build) and G2 (change-targeted tests) are PASSED for the exact revision being released. If either—or any other required check—is NOT RUN, BLOCKED or FAILED, keep the handoff BLOCKED and return to Verify. Scaffold/hash checks and "host build succeeded" are not substitutes. When the builder skill's gate helper is available, `scripts/gates.py --factory <root> --stage pre-merge --revision <rev>` must exit 0.

## Post-merge confirmation (required)
After an authorized merge/deploy, run G3: the smoke suite against the deployed URL for the merged revision. Record pass/fail, revision, URL, time and evidence in verification.md and release-handoff.md. If G3 fails or cannot run, surface it immediately to the release owner with evidence, follow the rollback plan within existing authority, and report the release as unconfirmed—never as done. When done videos or other release follow-up are enabled, run G3 first and produce the demo only after G3 passes.

## Exit gate
A prepared handoff (BLOCKED unless G1/G2 passed) or an explicitly authorized release confirmed by a passing G3. Never auto-approve/merge a PR or assume deployment permission.

Return: status, input/output revision, artifacts, checks actually run, unresolved risks, and next owner/action. Refer to files at the factory root; do not claim integration or execution occurred merely because a template exists.

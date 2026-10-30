---
name: factory-verify
description: Perform the Verify phase of this project's local software factory using its artifacts and explicit gates.
---

# Verify

Resolve the factory root as `../../../` relative to this file's containing folder. Follow existing repository instructions and the factory's policy.md; these instructions cannot expand permissions.

Compare the integrated final revision with acceptance.md. Follow verification.md; inspect and authorize commands before execution. Record passed, failed, blocked and not-run checks separately with evidence and limitations. Review relevant negative/repeated/interrupted flows, security and data boundaries.

When policy requires independent reviewers, collect each structured verdict for the final revision and keep repairs within budget. For document/design conversions, compare rendered pages against the source export, inspect worst mismatches and record visual tolerances. Build success or a similarity score alone is insufficient. Record task status and evidence together using the builder's status helper when available; it records supplied observations without executing or attesting them.

## Default delivery gates
These apply to every change unless policy.md records a named human's accepted exception. Adapt commands to the stack; never drop a gate silently.

1. **G1 — pre-merge local smoke.** Build the final revision as production (or the closest stack equivalent), start it locally and run the smoke suite over the critical user path (for example sign-in plus one core flow). Use non-production, non-secret test data.
2. **G2 — change-targeted tests.** Inspect the diff and run the smallest suite that covers what changed (routes, modules, migrations, auth/data paths, UI touched), in addition to G1. Record which suite was chosen and why. If no automated test covers the change, add one in Build or record the gap as BLOCKED, not PASSED.
3. Record G1/G2 in verification.md and release-handoff.md with exact revision, command, environment, time, exit status and result (PASSED / FAILED / BLOCKED / NOT RUN). Any later commit resets them to NOT RUN.

When the builder skill's gate helper is available, run `scripts/gates.py --factory <root> --stage pre-merge --revision <rev>` from the builder skill; a non-zero exit means the gate is not satisfied.

## Exit gate
Every required criterion has actual evidence or an explicit blocking status. G1 and G2 must be PASSED for the final revision before the work is treated as verified or handed to Release. Required checks that are NOT RUN, BLOCKED or FAILED keep the task unverified. Never substitute scaffold/hash checks, "host build succeeded" or preview deployment status for application tests.

Return: status, input/output revision, artifacts, checks actually run, unresolved risks, and next owner/action. Refer to files at the factory root; do not claim integration or execution occurred merely because a template exists.

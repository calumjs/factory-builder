---
name: factory-verify
description: Perform revision-bound pre-merge application verification and prepare post-release evidence handoffs.
---

# Verify

<!-- phase-compact:v1 -->

1. Compare the final diff with acceptance, research, verification rows and configured recipes. Follow the [Verify guide](../../../phase-verify-guide.md#run-the-pre-merge-checks) before running or recording checks.
2. Apply its persistence/parity, shared-contract, data-prerequisite and mapped-test reconciliation procedures wherever relevant. Run authorized checks still required for this stage (G1/G2 and applicable A/R); required missing, skipped or failed coverage blocks readiness. Record exact subject, environment, target, time, exit and durable evidence; assess pre-merge rows with gates.py, which executes no tests. Preserve optional waivers.
For enabled videos, follow the guide's current-trigger handoff procedure.
3. Follow the guide's [handoff procedure](../../../phase-verify-guide.md#hand-off) to map changed-feature post-action scope and unresolved assumptions. Recommend readiness only when all still-required pre-merge checks/reviews pass; otherwise hand off BLOCKED. Verification never merges or deploys.
4. Return: status, input/output revision, artifacts, checks actually run, blockers and risks, next owner/action. A template, plan or config proves nothing ran.

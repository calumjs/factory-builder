---
name: factory-release
description: Prepare a truthful readiness handoff, perform only authorized release actions, and confirm actual targets.
---

# Release

<!-- phase-compact:v1 -->

1. Prepare release-handoff.md even when blocked. Follow the [Release guide](../../../phase-release-guide.md#pre-action) for exact-subject readiness, provisioning prerequisites and separately authorized actions.
2. Before release work, follow its [single-owner and migration-ordering procedure](../../../phase-release-guide.md#coordinate-one-release-lane). After authorized action, follow [post-action confirmation](../../../phase-release-guide.md#post-action): reconcile feature/scenario scope, actors, actual target, required G3/A/R evidence and optional waivers. A filtered pass cannot hide required exclusions. Use the guide's failed-G3 procedure for retries; retain both subjects and failure history.
For enabled videos, follow the guide's current-trigger video procedure.
3. Exit with a truthful prepared handoff or confirmed authorized outcome, unresolved blockers and next owner. Report UNCONFIRMED/FAILED when required post-action checks cannot pass; incomplete review packages remain explicit.
4. Return: status, input/output revision, artifacts, checks actually run, blockers and risks, next owner/action. A template, plan or config proves nothing ran.

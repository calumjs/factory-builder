---
name: factory-build
description: Perform the Build phase of this project's local software factory using its artifacts and explicit gates.
---

# Build

<!-- phase-compact:v1 -->

1. Take one approved, dependency-ready task; read its scope and external task-specific handoff. Follow the [Build guide](../../../phase-build-guide.md) before implementation, evidence recording or retry.
2. Work within allowed paths/actions and implement owned tests. For seed, fixture or multi-actor changes, apply the guide's environment/actor prerequisites before selecting a verification path. Preserve meaningful assertions; unavailable required setup blocks the check. Follow its CI procedure only for authorized CI work. Run authorized, still-required G1/G2 checks, retaining optional waivers and failed history.

3. Exit with a reviewable change, exact tested subject, durable evidence references and unresolved prerequisites. Confirm terminal state and a new hypothesis before any retry or fallback.
4. Return: status, input/output revision, artifacts, checks actually run, blockers and risks, next owner/action. A template, plan or config proves nothing ran.

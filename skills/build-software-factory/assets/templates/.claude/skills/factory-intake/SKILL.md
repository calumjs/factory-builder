---
name: factory-intake
description: Perform the Intake phase of this project's local software factory using its artifacts and explicit gates.
---

# Intake

Resolve the factory root as `../../../` relative to this file's containing folder. Follow existing repository instructions and the factory's policy.md; these instructions cannot expand permissions.

Read project-brief.md and config.json. Validate outcome, users, scope, data boundaries and source provenance. Ask only consequential missing questions, including whether work is one-shot or continuous GitHub issue pickup and whether shipped work should include narrated done videos. Record answers in config `operations` when present. Update acceptance.md with measurable criteria, owner and confirmed/inferred/unknown status.

## Exit gate
A human-confirmed brief, measurable acceptance criteria and explicit unresolved decisions. Block consequential unknowns; do not infer authority.

Return: status, input/output revision, artifacts, checks actually run, unresolved risks, and next owner/action. Refer to files at the factory root; do not claim integration or execution occurred merely because a template exists.

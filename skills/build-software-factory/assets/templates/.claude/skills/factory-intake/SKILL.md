---
name: factory-intake
description: Perform the Intake phase of this project's local software factory using its artifacts and explicit gates.
---

# Intake

## Preflight
1. Follow launch-guide.md: pin the loaded builder version/source, confirm the helper files and the exact interpreter command against task permissions. Missing tooling is BLOCKED; a newer plugin does not migrate an older factory by itself.
2. Confirm all seven skills (six phases plus factory-run) are discovered at the intended path and settings source. Prose imitating a phase is not a Skill invocation. Do not copy skills globally or change launch routes to fix discovery; report it.

## Confirm the brief
3. Read project-brief.md, config.json and policy.md. Validate outcome, users, scope, data boundary and provenance. Ask only consequential missing questions, in small batches; label each answer confirmed, inferred or unknown. Unknown sources are not confirmation.
4. Read config.assumptions and the brief's recorded section. Keep labels, provenance and blocker labels as claims; update them only through the builder's reviewed assumptions/config/brief update.

## Design the checks
5. Choose stack-fitted G1 production-equivalent smoke and G2 change-targeted test designs from inspected scripts and CI. Greenfield: define the fixture, production-equivalent artifact, success and failure assertions, and a task to implement the invocation. Never invent commands.
6. Identify the actual release target, or record an explicit no-release scope. Checks that need a completed action are post-merge, with rationale.
7. When commands are actually known, record them as optional smoke_gates.checks (argv, environment label, env variable names only, web/artifact target, optional base_url_env). Uninspected commands stay designs.

## Operating preferences
8. Issue pickup: one-shot (default) or continuous. Continuous means around-the-clock polling or event-driven coverage unless the operator explicitly chooses a window with timezone and evidence; fit cadence to scheduler capability and budget. Recording it starts nothing.
9. Done videos: if enabled, ask whether triggers are pre_merge_preview (V2), post_g3_release (V1) or both; omission keeps release-only V1. Choose composition, voice, branding, captions and delivery scope from done-video-recipe.md.
10. Put proposed operational answers in approved scratch, preview the builder's update_operations.py, review the complete config/policy/manifest diff and apply only that plan. Broader brief or acceptance changes need their own reviewed diff.

## Exit
A confirmed brief, measurable criteria and explicit unresolved decisions — or a BLOCKED handoff for diagnosis.

---
name: factory-release
description: Prepare a truthful readiness handoff, perform only authorized release actions, and confirm actual targets.
---

# Release

## Pre-action
1. Prepare release-handoff.md, blocked or not, preserving evidence for diagnosis. Mark it READY FOR AUTHORIZED ACTION only when every still-required pre-merge check passes for the exact reviewed revision and required reviewer verdicts cover that revision. Run `gates.py --factory <root> --stage pre-merge --revision <rev>`.
2. Before first provisioning, verify framework, runtime, build and output settings against the project and current official provider guidance. Discover the live plan/SKU identifiers and record the selection, limits, cost, source and time; a free plan is not permission. Inventory permitted environment names (no values) and who manages each target.
3. Without publication authority, deliver the prepared handoff and stop.

## Post-action
4. Only after a separately authorized merge, deploy, install or publish: run G3, if still required, against the actual target and merged revision — the real URL for web targets, the installed or published artifact for everything else — plus required post-action A/R checks. Record result, target, revision, command or observation, time, exit status and evidence, then run `gates.py --factory <root> --stage post-merge --revision <merged-rev> --target <target>`. An optional G3 is reported WAIVED.
5. If a required post-action check fails or cannot run, report UNCONFIRMED/FAILED at once to the release owner with evidence, target, revision and the diagnosis or rollback decision needed. Roll back only within existing authority. An unknown target stays blocked; only accepted no-release scope records G3 NOT APPLICABLE with rationale.
6. Record the deployed subject SHA separately from any evidence-storage commit. If storing evidence redeploys, identify and separately confirm the newly deployed revision. A CI adapter's green pre-merge assessment is not deployment confirmation.

## Video (when enabled)
7. Read done_videos triggers in config: omitted means release-only V1; post_g3_release selects V1 here. If G3 is required it passes first; if optional, record its waiver. If V1 is required, record the authorized demo with shipped revision, target, artifact and time, following done-video-recipe.md: genuine target footage, scripted story, captions, provenance, watched and listened-to output, delivery only on an approved channel. Approval comes immediately before narration unless the current prompt asked for it. A script, silent draft or render is not a delivered demo; a blocked required demo stays blocked; V2 never substitutes.

## Exit
A truthful prepared handoff, or an authorized action confirmed by all still-required post-action checks (optional ones COMPLETED WITH WAIVERS), with unresolved assumption blockers and the next owner named. Report code readiness separately from an incomplete review package.

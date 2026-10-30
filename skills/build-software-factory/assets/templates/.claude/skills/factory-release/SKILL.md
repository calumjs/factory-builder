---
name: factory-release
description: Prepare a truthful readiness handoff, perform only authorized release actions, and confirm actual targets.
---

# Release

Resolve the factory root as `../../../` relative to this file's containing folder. Follow repository instructions and policy.md; these instructions expand no permissions.

## Pre-action
Prepare release-handoff.md even when blocked, preserving evidence for diagnosis. Mark it READY FOR AUTHORIZED ACTION only after G1/G2 and every required pre-merge A/R check pass for the exact reviewed revision and required reviewer verdicts are satisfied. Use the builder's gates.py --factory <root> --stage pre-merge --revision <rev> when available. NOT RUN, BLOCKED or FAILED is not ready. Future G3/V1 evidence does not block this stage. No publication authority means deliver the prepared handoff and stop; a passing gate never grants merge/deploy permission.

## Actual-target confirmation
Only after a separately authorized merge/deploy/install/publish action, run G3 against the actual target and merged revision. Web targets use the actual URL; CLI/library/package/document/data releases use the actual installed/published artifact or equivalent consumer path. Record result, exact target/revision, command/manual observation, time, exit status and evidence. Use gates.py --factory <root> --stage post-merge --revision <merged-rev> --target <actual-target>. Required post-action A/R checks also apply.

If a required post-action check fails or cannot run, report UNCONFIRMED/FAILED immediately to the release owner/orchestrator with evidence, actual target/revision and the diagnosis/rollback decision needed. Perform rollback only within its existing authority. An unknown target is blocked; only explicitly accepted no-release scope may record G3 NOT APPLICABLE with rationale.

## Enabled video and follow-up
Read the actual done_videos preference in policy/config. When enabled, use Verify's scoped handoff: G3 must pass first, then perform authorized narrated recording and record V1 with the shipped revision, actual target, artifact and time. Recording, storage and external publication are distinct scopes. A blocked or unavailable demo is reported explicitly and never silently omitted or fabricated. No video work is requested when disabled.

## Exit gate
Return a prepared handoff whose readiness is truthful, or an authorized action confirmed by all applicable post-action checks. CONFIRMED/DONE requires those checks and enabled V1; it never means PR approval/merge or deployment authority.

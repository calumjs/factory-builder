# Verification plan and evidence

Scaffold/hash checks, a successful build, lint/types, preview status, or test-file existence do not establish application verification. This file contains operator-supplied observations; the offline gate helper executes and attests nothing.

## Map the checks to this stack

Reuse inspected repository scripts, CI jobs, fixtures and test setup. G1 builds/packages the production-equivalent artifact and exercises a critical success path plus an expected failure; G2 chooses the smallest additional suite covering the diff. For CLI/library/data/document projects, use the equivalent installed artifact, import/API, transformation or rendered-output check. A web server or sign-in flow is not universal.

For greenfield, first design a non-secret representative fixture, production-equivalent preparation, one observable success and one expected-denial/failure assertion, cleanup and concrete invocation using the chosen stack. Add that bounded test implementation task before claiming readiness. Unconfirmed designs are not executable commands and remain NOT RUN/BLOCKED.

## Two stages

Pre-merge readiness needs every still-required pre-merge check PASSED for the exact reviewed revision. G1/G2 default to required, but explicit user waivers are respected and visibly reported, not tests-passed. Future post-merge checks may remain NOT RUN at this point. A blocked diagnostic handoff can always be prepared; it is not release-ready.

After the separately authorized action, a still-required G3 confirms the actual deployed URL or installed/published artifact at the merged revision. If the user made G3 optional, report WAIVED rather than requiring execution or claiming it passed. Report failures or inability to run a required check immediately for the release owner/orchestrator, retain evidence and request the diagnosis/rollback decision within existing authority. An outcome with optional checks is COMPLETED WITH WAIVERS, not a tests-passed claim.

## Recording rules

Optional structured smoke_gates.checks plans supply canonical JSON argv, an
environment label, variable names (never values) and a web/artifact target. Required
PASSED rows must match that command/environment/target; a match is still a supplied
claim, not execution or proof those variables were set. New observations retain the
actual subject. Use reviewed synchronized updates before changing configured plans.
Explicit video triggers create pre-merge V2 for pre_merge_preview and post-merge V1
for post_g3_release. Omitted triggers preserve release-only V1; disabled video adds
neither. Missing/wrong-stage expected rows remain errors even when optional.

Use the generated rows below. A1... tracks acceptance; R1... tracks selected research checks; V1 defaults required when done videos are enabled; users may explicitly waive it, and a required V1 follows G3 unless G3 was explicitly waived. Required extra checks may use X1...; promote permanent requirements into reviewed config/research so removal is detectable. Stage overrides for A/R require an operations check_stages rationale; post-action-only criteria must not be required before their action exists.

Replace a proposed design with the actual inspected command or explicit manual observation procedure. A PASSED record needs concrete environment, exact revision, evidence/artifact reference, actual target, ISO timestamp with timezone and exit status 0 (or manual for a genuinely manual observation). FAILED, BLOCKED or NOT RUN on a still-required check blocks its stage. Missing, malformed and duplicate rows remain errors even for optional defaults; stale or wrong-target evidence cannot satisfy a required check. Re-run after relevant revision/target changes; never fabricate evidence or treat a recorded claim as independently verified.

Expected G1/G2/G3 rows must remain present, but an explicit Required=no/false is a deliberate user waiver and is respected without extra approval. Optional checks are reported WAIVED, not tests-passed. A G3 NOT APPLICABLE record is allowed only for an explicitly accepted no-release scope with rationale in operations; an unresolved target is BLOCKED. Required confirmation for web and non-web releases needs the actual target; an explicit optional confirmation is reported WAIVED. Record statuses separately from authorization.

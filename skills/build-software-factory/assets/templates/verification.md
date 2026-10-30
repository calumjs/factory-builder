# Verification plan and evidence

Scaffold/hash checks, a successful build, lint/types, preview status, or test-file existence do not establish application verification. This file contains operator-supplied observations; the offline gate helper executes and attests nothing.

## Map the checks to this stack

Reuse inspected repository scripts, CI jobs, fixtures and test setup. G1 builds/packages the production-equivalent artifact and exercises a critical success path plus an expected failure; G2 chooses the smallest additional suite covering the diff. For CLI/library/data/document projects, use the equivalent installed artifact, import/API, transformation or rendered-output check. A web server or sign-in flow is not universal.

For greenfield, first design a non-secret representative fixture, production-equivalent preparation, one observable success and one expected-denial/failure assertion, cleanup and concrete invocation using the chosen stack. Add that bounded test implementation task before claiming readiness. Unconfirmed designs are not executable commands and remain NOT RUN/BLOCKED.

## Two stages

Pre-merge readiness needs G1/G2 and every required pre-merge acceptance/research check PASSED for the exact reviewed revision. Future post-merge checks may remain NOT RUN at this point. A blocked diagnostic handoff can always be prepared; it is not release-ready.

After the separately authorized action, G3 must confirm the actual deployed URL or installed/published artifact at the merged revision. Record failures or inability to run immediately for the release owner/orchestrator, retain evidence and request the rollback/diagnosis decision within existing authority. Do not report an unconfirmed release as done.

## Recording rules

Use the generated rows below. A1... tracks acceptance; R1... tracks selected research checks; V1 is required after passing G3 when done videos are enabled. Required extra checks may use X1...; promote permanent requirements into reviewed config/research so removal is detectable. Stage overrides for A/R require an operations check_stages rationale; post-action-only criteria must not be required before their action exists.

Replace a proposed design with the actual inspected command or explicit manual observation procedure. A PASSED record needs concrete environment, exact revision, evidence/artifact reference, actual target, ISO timestamp with timezone and exit status 0 (or manual for a genuinely manual observation). FAILED, BLOCKED, NOT RUN, missing, malformed, duplicate, stale or wrong-target records block the applicable stage. Re-run after relevant revision/target changes; never fabricate evidence or treat a recorded claim as independently verified.

G1/G2 cannot be deleted or marked optional. A G3 NOT APPLICABLE record is allowed only for an explicitly accepted no-release scope with rationale in operations; an unresolved target is BLOCKED. Applicable web and non-web releases still need actual-target confirmation. Record statuses separately from authorization.

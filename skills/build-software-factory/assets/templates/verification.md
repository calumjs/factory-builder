# Verification plan and evidence

Scaffold creation is not an application-test pass. Required checks begin NOT RUN.

## Default delivery gates (required unless policy.md records a human-accepted exception)

Every change passes these gates. Adapt the command and environment to the stack; never drop a gate silently. Record the exact revision; a later commit resets the gate to NOT RUN.

| Gate | Stage | Check/command | Environment | Required? | Revision | Result | Evidence / time / exit status |
|---|---|---|---|---|---|---|---|
| G1 | pre-merge | Local smoke against a production build (or stack equivalent): build, start, exercise the critical user path (e.g. sign-in plus one core flow) | local production build | yes | | NOT RUN | |
| G2 | pre-merge | Change-targeted tests: smallest suite covering what this change touched (changed routes, modules, migrations, auth/data paths) | local | yes | | NOT RUN | |
| G3 | post-merge | Confirmatory smoke against the deployed URL for the merged revision (same critical path as G1) | deployed target | yes | | NOT RUN | |

Result values: PASSED, FAILED, BLOCKED, NOT RUN. Only PASSED satisfies a gate. NOT RUN, BLOCKED or FAILED on G1/G2 blocks release handoff and merge recommendation. A FAILED or NOT RUN G3 marks the release unconfirmed: surface it immediately to the release owner with evidence, follow the rollback plan, and do not report the release as done (or produce a done video) until G3 passes.

Not substitutes: scaffold/manifest hash checks, "host/CI build succeeded", preview deployment status, type-check or lint alone, or a test file existing without an observed run.

## Acceptance and additional checks

| Acceptance ID | Check/command | Environment | Required? | Revision | Result | Evidence / time / exit status | Limitations |
|---|---|---|---|---|---|---|---|

Cover unit/integration/end-to-end checks only where appropriate; include failure and authorization paths. Inspect commands before executing them. A missing required check blocks release. Capture exact revision and recheck after later changes.

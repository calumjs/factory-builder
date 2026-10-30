---
name: factory-learn
description: Perform the Learn phase of this project's local software factory using its artifacts and explicit gates.
---

# Learn

1. Record the observed outcome and evidence in learning-log.md. Separate facts from hypotheses, name repeated failures, and propose the smallest useful improvement to context, tests, tools or workflow, with an owner and an evaluation measure.
2. Compare config.assumptions with what was observed: which confirmed, inferred or unknown claims held, which blockers remain. Propose reviewed changes to the hashed config and brief with selective manifest entries; do not promote a label or clear a blocker silently.
3. Check observed continuous-intake coverage against the operator's choice: an unrequested business-hours restriction is a defect to report and propose fixing. For video lessons, distinguish watched, delivered artifacts from scripts or render-only claims, keeping V1/V2 subjects and waivers intact.
4. Refresh the local overview with dashboard/README.md only when asked, to a snapshot outside this directory. Review source age, missing evidence and waived checks; counts are recorded claims, not throughput or liveness. Dashboard and status summaries deliberately omit private assumption text and sources. Propose project metrics only with an approved real source and adapter.
5. For a reusable improvement to the builder itself, read upstream-provenance.json, resolve the component's source from installed plugin metadata, and use the contribute-upstream skill to prepare a sanitized draft. Read the upstream's contribution policy and check for duplicates; any issue, comment, fork, push or PR needs scoped approval or an already-authorized standing instruction.

Coordinate shared evidence integration serially. Rebase a later evidence change onto
an accepted one and preserve both subjects' observations, unique task events and
learning entries; retain failures and resolve conflicts explicitly, never by blindly
choosing the newest row. The gate table has one current row per ID: retain previous
observations as history, select the subject being assessed and rerun the applicable
checks for that subject. A status writer's lock coordinates cooperating writes only;
it does not guarantee Git merges or exclude arbitrary concurrent editors.

For each reported test run, record the intended scope and what actually executed,
the subject, command or report, and passed, failed, skipped and not-run counts
separately. Record retries or flaky outcomes with their counting convention; do not
count retries as additional unique tests. If the runner does not provide a count,
record unknown rather than zero. A serial failure can leave later cases unexecuted:
report the incomplete scope, preserve the failure, and rerun the applicable checks
after repair before claiming the whole scope passed. A smaller smoke count does not
prove the full suite or a production check passed.

## Exit
A reviewed improvement proposal. No policy, permission, provider or production change is made here.

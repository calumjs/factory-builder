# Plan

## Challenge acceptance before decomposition

Fit a bounded gap check to the actual change before assigning Build work. Inspect
the relevant repository paths and tests against the draft criteria: missing edge
cases, undefined guardrails, unsupported code assumptions and unasked questions.
Record the inspected repository subject separately from the exact draft/digest;
unseen behavior stays unverified. Use the trusted installed builder's
`references/spec-challenge.md` for the procedure and task-specific record shape.

Choose critic scope and independence according to project risk, availability and
the existing authorized budget. Trivial work need not pay for two agents; record
not-selected or unavailable honestly. An actual independent critic returns
ACCEPT, ACCEPT-WITH-RESERVATIONS, REVISE or REJECT with evidence and severity.
Default to at most two revision rounds within the original budget. Revisions
invalidate an older draft's verdict; exhaustion never turns REVISE, REJECT or a
missing required critic into acceptance. Preserve every unresolved item in Open
Questions with owner, impact and affected work blocked where required.

For high-risk decisions, present the critic's verdict and unresolved questions to
the authorized decision owner. Record standing authority that already covers the
specific decision rather than inventing another approval; otherwise escalate the
uncovered scope. A critic verdict grants no execution, publication or adoption
authority. Keep task-specific notes outside this hashed factory. Acceptance edits
need a separately reviewed synchronized change that preserves IDs, waivers and
history; neither direct edits nor blanket re-hashing bypass that boundary.

## Decompose the accepted scope

1. Read the accepted brief, acceptance.md, tools.json, policy.md and config.assumptions. Resolve or explicitly retain each relevant uncertainty with the owner; a confirmed label is a recorded claim, not proof; it creates no automatic gate and never overrides an operator's waiver.
2. Break the work into owned tasks in task-plan.json: dependencies, acceptance IDs, allowed paths, expected evidence, budget share. Sequence tasks whose paths overlap. Copy the hashed worker-handoff.md to an approved task-specific location outside the factory before filling its ordered worker table. One worker is valid; candidates need their own authority, boundaries, availability evidence and stop conditions, and share the task's original budget. Verify a tool before enabling it; the plan launches nothing.
3. Map every task to the gate rows: G1 production-equivalent pre-merge smoke, G2 change-targeted tests, and G3 post-action confirmation on the actual URL or published artifact where applicable. Deliberate optional rows stay visible as WAIVED. Post-action evidence is never a pre-action dependency. If the project lacks a smoke suite, plan it first.
4. Reuse structured smoke recipes from config when present: inspect argv, environment label, variable names and target, then assign the still-required tests. Explicit video triggers map pre_merge_preview to V2 and post_g3_release to V1 with independent subjects and evidence.
5. Fit test design to the promised properties and risk. For retry idempotency or durable persistence, plan allowed-ID edge cases, retry/restart/removal semantics and disposable partial, zero and failed-write tests against the actual storage contract; add independent risk-focused review when risk and budget warrant. Do not narrow acceptance silently or impose a universal fault suite.
6. Assign owners and real repository paths for application tests, CI wiring and any test-to-acceptance map. Reuse existing commands; where absent, plan their implementation and execution. These are project deliverables outside this directory.
7. Fit the activity overview to the operators: read dashboard/README.md, choose evidence and freshness, reuse existing UI where useful, plan authorized adapters as owned tasks. Missing metrics stay unavailable; the overview is not a control surface.

## Trace changed shared contracts

Keep one canonical row per acceptance ID and configured stage. Do not create a
second A-row with the same ID to attach production evidence. Plan G3 references to
the exact acceptance checks and observed artifacts, or define a distinct reviewed
post-action criterion with its own unique ID and stage rationale. The optional
acceptance-links record aids traceability; a reference never establishes that the
linked check ran or passed. Preserve each observation's subject, actual target,
result and evidence, including explicit waivers and failed history.

When work changes a shared serialized shape or selection rule (for example export columns, query prefixes, event kinds or deletion filters), inspect the existing producers, consumers and tests before assigning implementation. Search both the contract symbols and representative old values, including exact headers, field counts, parsers, snapshots and fixture builders; follow references beyond the new feature's tests. Record the searched scope and any consumers whose compatibility remains unknown.

In the task's plan or handoff, record the old and intended behavior, producer/consumer paths, affected existing test paths and assertions, and the compatibility decision for each: update an obsolete expectation, retain a still-valid assertion and run it, or investigate an unresolved dependency. Appending a field can break a strict consumer; it does not require editing every consumer. Preserve assertions for behavior that must remain compatible rather than weakening them to accept the new output.

Assign required changes to an owner and allowed paths, link their acceptance IDs, and include the affected existing tests alongside new tests in the planned G1/G2 evidence and any project test map. Reuse the project's map format and commands; a search result or mapped path is not evidence that a test ran. A change with no shared-contract impact needs no extra inventory.

## Exit
For incremental work against existing acceptance, the installed builder's incremental-workflow.md describes preview-first task and scoped-record work. A scoped verdict is separate from whole-project readiness. New criteria require separately reviewed synchronized contract changes; do not silently add them.

A dependency-valid plan, mapped acceptance criteria, feasible budgets and explicit human approval points. Planning launches no workers.

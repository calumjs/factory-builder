---
name: factory-plan
description: Perform the Plan phase of this project's local software factory using its artifacts and explicit gates.
---

# Plan

1. Read the accepted brief, acceptance.md, tools.json, policy.md and config.assumptions. Resolve or explicitly retain each relevant uncertainty with the owner; a confirmed label is a recorded claim, not proof; it creates no automatic gate and never overrides an operator's waiver.
2. Break the work into owned tasks in task-plan.json: dependencies, acceptance IDs, allowed paths, expected evidence, budget share. Sequence tasks whose paths overlap. Use worker-handoff.md for delegation. Verify a tool before enabling it.
3. Map every task to the gate rows: G1 production-equivalent pre-merge smoke, G2 change-targeted tests, and G3 post-action confirmation on the actual URL or published artifact where applicable. Deliberate optional rows stay visible as WAIVED. Post-action evidence is never a pre-action dependency. If the project lacks a smoke suite, plan it first.
4. Reuse structured smoke recipes from config when present: inspect argv, environment label, variable names and target, then assign the still-required tests. Explicit video triggers map pre_merge_preview to V2 and post_g3_release to V1 with independent subjects and evidence.
5. Fit test design to the promised properties and risk. For retry idempotency or durable persistence, plan allowed-ID edge cases, retry/restart/removal semantics and disposable partial, zero and failed-write tests against the actual storage contract; add independent risk-focused review when risk and budget warrant. Do not narrow acceptance silently or impose a universal fault suite.
6. Assign owners and real repository paths for application tests, CI wiring and any test-to-acceptance map. Reuse existing commands; where absent, plan their implementation and execution. These are project deliverables outside this directory.
7. Fit the activity overview to the operators: read dashboard/README.md, choose evidence and freshness, reuse existing UI where useful, plan authorized adapters as owned tasks. Missing metrics stay unavailable; the overview is not a control surface.

## Trace changed shared contracts
When work changes a shared serialized shape or selection rule (for example export columns, query prefixes, event kinds or deletion filters), inspect the existing producers, consumers and tests before assigning implementation. Search both the contract symbols and representative old values, including exact headers, field counts, parsers, snapshots and fixture builders; follow references beyond the new feature's tests. Record the searched scope and any consumers whose compatibility remains unknown.

In the task's plan or handoff, record the old and intended behavior, producer/consumer paths, affected existing test paths and assertions, and the compatibility decision for each: update an obsolete expectation, retain a still-valid assertion and run it, or investigate an unresolved dependency. Appending a field can break a strict consumer; it does not require editing every consumer. Preserve assertions for behavior that must remain compatible rather than weakening them to accept the new output.

Assign required changes to an owner and allowed paths, link their acceptance IDs, and include the affected existing tests alongside new tests in the planned G1/G2 evidence and any project test map. Reuse the project's map format and commands; a search result or mapped path is not evidence that a test ran. A change with no shared-contract impact needs no extra inventory.

## Exit
For incremental work against existing acceptance, the installed builder's incremental-workflow.md describes preview-first task and scoped-record work. A scoped verdict is separate from whole-project readiness. New criteria require separately reviewed synchronized contract changes; do not silently add them.

A dependency-valid plan, mapped acceptance criteria, feasible budgets and explicit human approval points. Planning launches no workers.

# Fit verification to the promises and failure modes

A passing happy-path suite and smoke are evidence for their tested paths, not
proof of every promised property. When intake promises idempotency, durable state,
recovery or untrusted identifiers, Plan should assign a risk-focused test design
and an independent implementation review when warranted by risk/budget. For a
simple unrelated project, choose its relevant risks instead of importing this
entire matrix. The examples below are proposals to adapt, not mandatory new gates.

## Caller identifiers and retry semantics

Define the documented identifier alphabet and replay/conflict/removal behavior.
Test allowed boundary values through the actual public interface, persistence
round-trip and fresh-process restart. In JavaScript dictionary implementations,
consider keys such as __proto__, constructor and hasOwnProperty when the promised
alphabet allows them. Inspect inherited properties, own-key checks, lookup/insert,
serialization and reloaded representation. Choose an appropriate Map, null-prototype
dictionary or other fitted design, and prove its persisted round-trip. Do not fix
an implementation defect by silently narrowing accepted IDs. Other stacks need
their equivalent collision/normalization/encoding cases, not JavaScript-specific APIs.

Test repeated requests after restart and after removal according to the accepted
contract: replay identity, conflict behavior, tombstone/retention policy and visible
side effects. Resolve ambiguous acceptance with the owner; do not invent permanent
retention or deletion semantics. Distinguish independent process retries from
repeating a call against the same in-memory instance.

## Durable persistence and fault injection

Read the actual storage API contract and platform/version behavior. In a disposable
fixture, exercise partial/short progress, repeated short writes, zero progress and
write failures at the relevant pre-commit boundaries; include multibyte data when
the contract is byte-based. A process-kill-before-rename test covers a different
failure mode and cannot substitute for checking write completion. Preserve the
previous committed state on incomplete preparation and verify readable state after
restart, honest exit/error reporting and cleanup/retry behavior. Never inject faults
against real production data or mutate platform protections for a test.

For Node fs.writeSync, the return value is a byte count. Inspect the chosen overload,
buffer/offset/encoding handling and error path; prove complete progress or abort
before replacing committed state. Fsync/rename alone does not prove all intended
bytes were written. Do not claim universal power-loss durability from a generic
rename pattern: use the actual filesystem/database durability guarantees and tests.

## Discovery, repair and truthful re-gating

For task-specific secret/connection-string checks, use the generated
connection-string-review.md or [the bundled review guide](../assets/templates/connection-string-review.md).
R1 is selected research, not a hardcoded secret rule. Separate detection from
reviewed synthetic-fixture classification; hostnames, usernames and documentation
paths never establish an exemption. Test mixed and unknown-provenance cases with
invented values, preserve coverage and keep actual suspected credentials out of
logs/evidence. Criterion changes need review and fresh exact-subject observations,
not an old failure relabeled as passing or a silently dismissed scanner alert.

Keep the reproducer, exact failing subject, expected/actual result and durable
non-secret evidence. Record discovered required failures as FAILED/BLOCKED even
if an earlier suite passed; do not hide them behind counts or rewrite them as PASS.
Respect intentional optional rows as WAIVED with the failure retained. Repair on
a new exact subject revision, review the final diff, and rerun the relevant targeted,
acceptance and production-equivalent checks for that subject before restoring its
readiness. Retain old failures as history. Mixed old/new subject rows cannot certify
the repaired revision. A local record helper validates claims, not application truth.

Primary references read 2026-10-30 (check the installed version during a real task):
[Node24 filesystem contracts](https://nodejs.org/docs/latest-v24.x/api/fs.html#fswritesyncfd-buffer-offset-length-position),
[Object.create/null prototypes](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/create).
The reference facts guide project-specific tests; the Python builder does not run
Node code, inject application faults or guarantee generated application correctness.

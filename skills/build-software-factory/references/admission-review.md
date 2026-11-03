# Recorded issue-admission review

Optional `operations.admission` records explicit issue-start, in-flight, identity
and cost choices. The installed `scripts/admission_review.py` compares bounded
**supplied claims** with that policy. It never authenticates an actor, verifies
billing/completeness, reserves capacity, fetches evidence, dispatches a worker or
enforces spending. A role/capability predicate grants no action authority.

Without `admission`, legacy controls and Run behavior are unchanged. Existing
`autonomy.max_items_per_hour` counts dispatched **task IDs**, and
`budget.max_workers` bounds recorded worker/task capacity; neither is redefined
as an issue count. The original task cost/time/repair budget still applies. An
item may involve multiple tasks, workers and attempts; this reviewer does not
enforce those task budgets or translate amounts to a provider CLI flag.

## Explicit policy choices

This synthetic example belongs at `operations.admission`. Its values are not
operator defaults and activate nothing:

```json
{
  "version": 1,
  "status": "specified",
  "repository": "SYNTHETIC/example",
  "identity": {"kind": "label_actor_capability", "capability": "write"},
  "starts": {"maximum": 8, "window": "calendar_day", "timezone": "UTC"},
  "max_in_flight_items": 2,
  "completion": "draft_pr",
  "costs": {
    "currency": "USD",
    "max_per_item": "3.00",
    "period": {"maximum": "20.00", "window": "calendar_month", "timezone": "UTC"}
  },
  "snapshot_max_age_seconds": 300
}
```

All keys are required; `version` is integer 1. `status: draft` permits unresolved
choices as null and always blocks issue proposals. `specified` requires every
choice. Supplied non-null draft values still validate; unknown keys are rejected.
Counts are integers from 0 to 1,000,000, snapshot age is 1 to 86,400 seconds, and
zero limits deny proposals even when requested cost is zero. Monetary values are
nonnegative decimal **strings**, up to 12 integer and 6 fractional digits, with
no exponent, sign or leading zero padding. Currency is a three-uppercase-letter
code equal to the existing budget currency; syntax validation is not currency
verification. There is no exchange-rate conversion or implicit USD assumption.

Starts use an explicit calendar-day timezone. Spend uses a calendar day or month,
independently chosen. UTC uses the standard library without an external timezone
database; unavailable other IANA data yields UNKNOWN, never installation or a
substituted timezone. Calendar days may be 23 or 25 hours at DST changes. The
windows include their start and exclude their end.

Identity has exactly one of these shapes:

- `{"kind":"legacy_submitters"}`: match the issue author against the existing
  nonempty `autonomy.allowed_submitters` list.
- `{"kind":"label_actor_accounts","accounts":["chosen-account"]}`: match the
  readiness-label event actor against explicit unique accounts (1–100 entries).
- `{"kind":"label_actor_capability","capability":"write"}`: require a current
  supplied permission observation for the **same label actor** and repository.

The two replacement modes require `autonomy.allowed_submitters: []`; conflicting
rules are refused, not unioned. The issue author and label actor remain separate
identities. Account comparisons are exact. The capability observation is a claim
to review, not proof that a provider checked it or permission to publish/deploy.
Bounded, enabled continuous-intake metadata is also required for proposals, but
does not prove that a live dispatcher exists.

`completion` is explicitly `draft_pr`, `merged`, `shipped` or `owner_confirmed`.
It identifies the terminal event for the chosen **admission cycle**. A completed
draft-PR cycle is not a shipped feature. Reopening/re-admitting after that terminal
event requires a new cycle and consumes a new start; a retry of the same active
cycle does not consume another start. It still consumes cost and worker resources.

## Snapshot schema and evidence trust

The input is private JSON outside the factory, at most 1 MiB, 1,000 cycles and
100 requests. Identifiers/references are bounded printable strings; duplicate
JSON keys, ambiguous identities, malformed timestamps and non-finite numbers are
refused. The helper never opens a supplied source/evidence reference.

Exact top-level keys:

| Key | Contents |
|---|---|
| `version` | Integer 1 |
| `repository` | Exact configured admission/intake repository |
| `policy_sha256` | SHA-256 of the admission object serialized with sorted keys, compact separators and ASCII escapes |
| `observed_at` | Aware ISO timestamp, no later than review time and within configured freshness |
| `coverage` | `starts_since`, `complete`, `source_reference` |
| `period` | `start`, `end`, `spent`, `reserved`, `accounting_complete`, `accounted_through`, `source_reference` |
| `cycles` | Array of cycle records below |
| `requests` | Array of proposed request records below |

`coverage.complete` must be literal true and `starts_since` must cover the current
calendar-day boundary. The supplied inventory must include **every** current-day
admission (completed ones still count), all active/uncertain cycles and all
outstanding liability. No entry means zero only under that explicitly supplied
complete-inventory claim, whose truth the helper cannot establish.

`period.start`/`end` must match the current resolved accounting window. `spent` is
measured cost incurred within that window across all relevant cycles, including
completed ones. `reserved` includes **all** outstanding cycle liability, even for
cycles admitted before the current period. `accounting_complete` must be literal
true and `accounted_through` the same instant as `observed_at`. This asserts that
period costs are accounted through that time and that every delayed, unsettled or
otherwise unresolved charge remains conservatively reserved. If the adapter
cannot establish this, use false/null and retain UNKNOWN. A fresh timestamp alone
is not accounting completeness; nothing resets uncertain liability at midnight.

Every cycle has exactly:

```text
issue_id, cycle_id, admitted_at, state, completed_at, completion, spent, reserved, evidence
```

`spent` is the cycle's lifetime measured cost across all attempts, unlike the
period total. Current-period admissions cannot report lifetime spend exceeding
the aggregate period spend. `reserved` is outstanding liability, not already
measured spend; the sum across supplied cycles must equal `period.reserved`.
Never count the same amount as both paid and reserved. An authorized accounting
adapter must reconcile settlements, without dropping unresolved charges. No
negative credits/refund arithmetic is supported by this version.

State is `active`, `completed` or `unknown`. A completed cycle needs the exact
configured completion, evidence reference, ordered `admitted_at <= completed_at
<= observed_at`, and zero outstanding reservation. Active/unknown cycles have
null completion fields and hold in-flight capacity. Unknown is not terminated;
expiry, an empty transcript or lack of a marker cannot free its slot. Conflicting
unresolved cycles for one issue are refused.

Every request has exactly:

```text
request_id, issue_id, cycle_id, kind, author, event, permission, reserve
```

`kind` is `start` or `retry`; `reserve` is an additional proposed cost allocation.
Request, issue and cycle identities must be unambiguous: one request per issue
and per cycle in an assessment, unique request IDs, and no shared event IDs.
`author` must equal the normalized current issue's `submitter`. The existing
repository, ready/excluded-label and unresolved-dependency rules still apply.

`event` is null or exactly `id`, `label`, `actor`, `occurred_at`; actor modes need
it, and its label must match the current ready-label policy. `permission` is null
or exactly `actor`, `capability`, `decision`, `observed_at`, `reference`. Capability
mode needs `write`, decision `allowed` and the same event actor, with a fresh
observation no later than snapshot time. Denied/unknown/missing observations do
not pass. Account modes require permission to be null rather than ignoring an
unexpected authorization record.

A start cannot reuse any cycle ID or bypass an active/unknown cycle for its issue.
A retry must name the exact active issue/cycle pair. Completed or unknown cycles
cannot be retried as active. Requests are processed in stable issue/cycle/request
order, reducing only hypothetical allowance within that one response. Subsequent
invocations make no durable deduplication or exclusion guarantee.

## Commands and results

Use the verified installed builder with an approved interpreter. Run already
prints `admission_review.policy_sha256` when a policy exists but no snapshot was
supplied, so an authorized adapter can bind its snapshot without guessing a hash:

```text
python scripts/run.py --factory <factory> select --issues <current-issues.json> --issue-policy <label-policy.json>
python scripts/run.py --factory <factory> select --issues <current-issues.json> --issue-policy <label-policy.json> --admission-snapshot <snapshot.json>
python scripts/admission_review.py --factory <factory> --issues <current-issues.json> --issue-policy <label-policy.json> --snapshot <snapshot.json>
```

`plan` accepts the same snapshot flag. Missing/malformed inputs suppress new-policy
issue candidates; they never fall back to legacy author membership. Existing task
selection and Run's task-oriented `proceed` field remain separate. Satisfied
request decisions retain request/issue/cycle IDs, kind and allocation and are
intersected with Run's current eligible issue set. No observations are fabricated
from old run records, and no reservation file is written.

Result states are `RECORDED_POLICY_SATISFIED`, `BLOCKED`, `UNKNOWN` (or
`NOT_CONFIGURED` for a direct review without policy). Every result includes
`enforced: false` and `independently_verified: false`. The standalone CLI exits 0
when at least one request has a satisfied recorded review, 1 otherwise, and 2
for unreadable/invalid CLI inputs. Read per-request decisions; a batch may contain
both satisfied and blocked requests. Run retains its existing exit conventions.

A satisfied result is **not** a reservation or launch authorization. Before live
admission, an independently authorized dispatcher must verify sources/current
permission, atomically reconcile actual starts and active work, reserve capacity
and cost, and honor the real stop/worker/task budgets. Never pass the full item
ceiling independently to every parallel attempt. This implementation provides no
provider adapter, credential action, live rate/spend control or setting change.

Existing factories need [reviewed compatible copied operations and readiness
runtimes](admission-runtime-migration.md) when adopting the new policy. Preserve
custom code and original records; use the reviewed migration path rather than
copying helpers or rebaselining. The installed assessor is not part of the read-only
dashboard bundle.

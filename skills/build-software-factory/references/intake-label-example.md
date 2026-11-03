# Proposed issue labels and release ownership

This is a generic convention to review for a project, not installed configuration.
Reuse compatible existing labels. Creating labels, changing issue state, admitting
work and starting a watcher each need their own existing scoped authority. See
[operations-config.md](operations-config.md), [running.md](running.md) and
[operation.md](operation.md). No label grants authority or proves exclusion.

| Proposed label | Meaning and owner | Evidence required before the owner changes it |
|---|---|---|
| `factory:queued` | Intake owner holds a dependent or unreviewed request | Named dependencies, scope and next decision; no dispatch |
| `factory:ready` | Intake owner proposes eligibility | Accepted scope/submitter, dependencies reconciled and paths/resources reviewed |
| `factory:in-progress` | Authorized dispatcher records admitted work | Actual task, worker/run ID and verified exclusive admission |
| `factory:pr-open` | Build owner records a reviewable PR | Actual PR URL, branch and subject revision; not merge or deployment evidence |
| `factory:merged` | Release owner records the merge | Actual merge identity and resulting subject; automatic issue closure alone is insufficient |
| `factory:shipped` | Release owner reconciles the completed release | Actual published/deployed subject and target, required post-action checks and delivery evidence, with explicit optional waivers |
| `factory:rejected` | Intake owner records an out-of-scope decision | Reason and decision owner; no automatic retry |
| `factory:paused` | Operator requests a stop within the agreed policy | Any open issue with this label stops new proposals repository-wide in the example below |

The state labels are mutually exclusive in the adopted convention; `paused` is a
separate stop signal. Reconcile contradictory labels instead of interpreting them
as success. Map queued/ready to task `pending` only once an accepted task exists;
active work maps to `in_progress`, a real impediment to `blocked`, and verified
completion to `done`. Issue labels and task status are different records.

Promote `queued` to `ready` only after the intake owner reviews each dependency's
required outcome and evidence, refreshes the combined base revision, checks path
and shared-resource overlap and confirms remaining scope/budget. A closed issue or
merged PR is not necessarily a shipped dependency. Do not clear `depends_on` merely
to select work; retain the reviewed dependency history outside the factory. Recheck
at admission: simultaneous read-only proposals do not reserve work. Local locks or
labels alone do not provide cross-worker exclusion.

## Read-only reference query

For the authorized repository read, use the explicit-repository export in
[running.md](running.md), including **all open issues**, not just ready issues.
Verify pagination/completeness, repository identity, snapshot freshness, dependencies
and prior processed history. A capped export, failed page, unknown dependency or
unverified history means stop. The example bounds its supplied snapshot at 1,000
issues; use a separately reviewed design for larger repositories. GitHub closed
issues are excluded from this snapshot, but their dependency/release history still
needs reconciliation. No export or network command runs from this reference.

Here is a proposed policy object for the existing `run.py` API. Replace its
synthetic repository with the independently verified configured scope:

```json
{"repository":"SYNTHETIC/example","ready_label":"factory:ready","excluded_labels":["factory:queued","factory:in-progress","factory:pr-open","factory:merged","factory:shipped","factory:rejected","factory:paused"]}
```

The Python example runs with the trusted builder's `scripts` directory on its
import path. Pass the `root, config, plan` returned by `run.load`, an approved runs
path outside the factory, a normalized open-issue snapshot and the reviewed policy.
`snapshot_verified=True` records the caller's completed checks; it performs none.
It returns proposals only, leaving the snapshot, factory and run records untouched.
The existing selector supplies submitter/dependency filters, stable timestamp/ID
ordering, STOP/environment handling and recorded rate/capacity calculations.

```python
from run import select


def propose_intake(root, config, plan, runs, issues, policy, now, *, snapshot_verified):
    if snapshot_verified is not True:
        raise ValueError("Verify complete repository snapshot and dependency/history evidence first")
    if not isinstance(issues, list) or len(issues) > 1000:
        raise ValueError("Expected a bounded complete open-issue snapshot")
    for issue in issues:
        if not isinstance(issue, dict) or not isinstance(issue.get("labels"), list):
            raise ValueError("Cannot establish repository-wide pause state")
        if any(not isinstance(label, str) for label in issue["labels"]):
            raise ValueError("Cannot establish repository-wide pause state")
    if any("factory:paused" in issue["labels"] for issue in issues):
        return {"issue_ids": [], "reason": "repository pause signal; no new proposals"}
    result = select(root, config, plan, runs, issues=issues, now=now, issue_policy=policy)
    capacity = result["capacity"]
    # Existing task proposals consume this pass's advisory allowance first.
    limits = [capacity["available"]]
    if capacity["rate_remaining"] is not None:
        limits.append(capacity["rate_remaining"])
    slots = max(0, min(limits) - len(result["candidates"]))
    return {"issue_ids": [item["id"] for item in result["issues"]["eligible"][:slots]],
            "reason": "advisory only; recheck live policy and exclusive admission before dispatch",
            "selection": result}
```

This intentionally caps proposals by `max_items_per_hour` remaining in recorded
history; those supplied records are not independently verified admissions. An
authorized live dispatcher must enforce actual rate, budget, concurrency and stop
controls atomically and recheck their current values. The wrapper's global pause
rule is an example addition, not behavior already installed in `run.py`. It cannot
cancel an active worker; use only an authorized stop control or owner intervention.

## `pr-open` to `merged` to `shipped`

Release owns this reconciliation, including issues auto-closed by a merge. A
done-video routine returns its revision/target-bound artifact and observation to
Release; it does not independently declare the issue shipped or change labels.
After verifying the real merge, Release can propose removing `pr-open` and applying
`merged`. After the actual authorized delivery, reconcile the actual deployed
subject (not merely the PR head), G3 and any required V1/named post-action rows.
Only then propose `merged` to `shipped`. Failed, unknown or missing required
evidence retains `merged` with a blocked/unknown handoff; preserve failure history.

An explicitly optional G3 or V1 stays **WAIVED with its underlying observation**;
do not call it passed or impose another approval merely to change requiredness.
A release with optional waivers may be shipped when the actual delivery and all
still-required conditions are evidenced; record the waivers beside that claim.
A preview deployment/video does not establish the production outcome. A no-release
change uses its reviewed completion meaning rather than inventing a deployment.
Label edits are separately authorized bookkeeping, never the evidence themselves.

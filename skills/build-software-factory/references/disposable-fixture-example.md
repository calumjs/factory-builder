# Run-scoped fixture teardown proposal

Use this pattern when a smoke, feature or done-video check can write data. During
intake, identify the actual target/store, write effects, authorized actors and
cleanup owner, then choose: read-only checks; explicitly authorized namespaced
writes with teardown; or an authorized disposable representative target. A preview
pass covers that target only, not a required production check. Missing safe setup
leaves a required check BLOCKED/NOT RUN; an explicitly optional check stays WAIVED.
See [gates.md](gates.md), [done-videos.md](done-videos.md) and the generated
release-handoff's data-written/cleanup/residue fields.

For a writing recipe, generate a new unpredictable run ID for **each attempt**, for
example `fixture-` plus a UUID. Bind it to the verified target, test subject and
owner before creating fictional data. Names such as `SMOKE-<run-id>` aid diagnosis,
but a name prefix alone never authorizes deletion. Use a dedicated immutable
ownership marker and exact created IDs. Capture dependent resources (movements,
attachments, locations) too; review cascade effects and delete child-first only
within the authorized scope. Keep fixture receipts/journal outside the factory in
approved private storage, with no credentials or real user data.

## Concrete teardown-step example

This synchronous Python example is an adapter contract for a project-owned test
recipe, not an installed cleanup engine. Call it from the framework's teardown or
the recipe's cleanup step, including when assertions fail. Each receipt is an
observed create result for this run: `id`, exact `target`, `run_id` and a non-secret
immutable `owner_token` echoed by the trusted application. Record create intent
durably **before** the request and its receipt immediately afterwards. If creation
may have succeeded without a receipt, retain that unresolved intent: do not infer
its ID or compensate by scanning/deleting a prefix.

The authorized project's adapter must implement `delete_if_owned(receipt)` as an
atomic conditional delete binding ID, target, run ID and owner token, returning
`deleted`, `absent` or `ownership_mismatch`. A separate read then blind delete is
unsafe. `is_absent(receipt)` must return a real boolean from an authorized read of
the exact same target/ID, never translate a permission or network error into
absence. Configure bounded timeouts and response sizes. Review the adapter and
prove its conditional semantics in an authorized disposable target before use;
when the API cannot provide them, use a documented owner-led manual cleanup.

```python
def teardown_created(adapter, *, target, run_id, receipts):
    def token(value):
        return (isinstance(value, str) and 0 < len(value) <= 256
                and value == value.strip() and value.isprintable())

    if not token(target) or not token(run_id):
        raise ValueError("Explicit target and run identity required")
    if not isinstance(receipts, list) or len(receipts) > 100:
        raise ValueError("Review an exact bounded receipt list before cleanup")
    seen = set()
    for receipt in receipts:  # Validate the entire plan before the first adapter call.
        if (not isinstance(receipt, dict)
                or set(receipt) != {"id", "target", "run_id", "owner_token"}
                or any(not token(value) for value in receipt.values())
                or receipt["target"] != target or receipt["run_id"] != run_id
                or receipt["id"] in seen):
            raise ValueError("Ambiguous or out-of-run cleanup receipt")
        seen.add(receipt["id"])
    outcomes = []
    for receipt in receipts:  # Caller supplies reviewed child-before-parent order.
        try:
            result = adapter.delete_if_owned(dict(receipt))
            if result == "ownership_mismatch":
                status = "BLOCKED_OWNERSHIP"
            elif result in ("deleted", "absent") and adapter.is_absent(dict(receipt)) is True:
                status = "CLEANED"
            else:
                status = "UNKNOWN"
        except Exception:
            # Retain uncertainty without publishing potentially secret exception text.
            status = "UNKNOWN"
        outcomes.append({"id": receipt["id"], "cleanup": status})
        if status != "CLEANED":
            # Do not proceed to a parent/cascade after an unresolved child.
            outcomes.extend({"id": item["id"], "cleanup": "NOT_ATTEMPTED"}
                            for item in receipts[len(outcomes):])
            break
    return outcomes
```

The caller must retain the original test failure and cleanup outcomes separately;
cleanup success cannot turn a failed feature assertion into PASS. All exact IDs
must be confirmed absent and every create intent reconciled before saying all data
was cleaned. An empty receipt list proves nothing about unresolved writes. A hard
kill, timeout or lost journal can prevent teardown entirely: record UNKNOWN and
handoff the run's exact scope to the named cleanup owner. A `finally`/`afterEach`
hook is not a crash guarantee. Retrying cleanup uses the same receipt identities;
retrying the test creates a new run ID. Never delete older runs or user records.

## Evidence and video reuse

Attach a private, non-secret observation to the existing G3/named check evidence
and release handoff; there is no new gate-table column or schema:

```text
SYNTHETIC example, not an observed run
Subject / actual target / test and attempt: <exact identities>
Data written to production: YES / NO / UNKNOWN (with observation)
Run ID / create-intent and exact-ID receipt reference: <private evidence>
Feature assertions: PASSED / FAILED / BLOCKED / NOT RUN
Cleanup: CLEANED / PARTIAL / BLOCKED / UNKNOWN; per-ID outcomes: <evidence>
Residue or uncertain writes / cleanup owner / next authorized action: <details>
Requiredness: required, or WAIVED with the underlying observation retained
```

Use this same fixture ownership and cleanup procedure for genuine video captures,
with fictional data and its own attempt identity or an explicitly shared reviewed
fixture lifecycle. Coordinate with the release owner; a video routine does not
gain deletion rights or cross-worker exclusion from a run ID or local lock.
Record evidence before teardown removes a demonstrated fixture, without capturing
secrets. Data written is YES even after complete cleanup. A successful assertion
does not hide partial cleanup; report residue and leave any required hygiene
condition unsatisfied. Do not auto-clean production merely because this example
exists. Project adapter implementation and live verification remain separate work.

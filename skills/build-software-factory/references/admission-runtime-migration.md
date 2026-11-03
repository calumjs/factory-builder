# Admission metadata in existing copied runtimes

The optional [recorded admission policy](admission-review.md) needs compatible
copied `dashboard/operations.py` and `dashboard/readiness.py` when a factory has
a dashboard bundle. Older operations validation rejects the section; older
readiness can omit its advisory even after operations is updated. A successful
manifest check alone does not establish support for either consumer.

Use the installed builder's [reviewed operations update](existing-factory-update.md).
For a known pristine older bundle, preview the intended operations patch with
`--context-runtime`. That existing flag updates known context helpers and includes
operations/recipe compatibility. Review every proposed helper and manifest change;
older bundles may need additional established migration flags. `--gate-runtime`
alone updates operations but cannot make an older readiness helper understand
admission. No new admission-specific flag is needed.

```text
python <trusted-skill-root>/scripts/update_operations.py --factory <factory-root> --operations <private-scratch>/operations-update.json --context-runtime
```

Use the approved absolute interpreter and trusted builder path. The patch contains
the explicitly chosen `admission` section and any necessary synchronized autonomy
or intake choices; the policy reference gives its schema. Do not put admission
observations, credentials or billing records into this configuration patch.
Review the preview, then repeat the same options with
`--apply --approve-plan <exact-reviewed-plan-digest>` within existing local-write
authority. A preview changes nothing, creates no backup, and activates no worker.

Exact helpers published through v1.27 are recognized for explicit migration.
Without a new admission policy or a runtime opt-in, unrelated updates preserve
those legacy bytes. If admission is present in the proposed configuration,
both proposed copied consumers must match the installed builder's supported
normalized source, including when the patch changes another section or changes
nothing. Already supported consumers need no redundant migration flag. Custom or
unsupported helpers are preserved and require a narrow manual compatibility
review; never replace them automatically or recalculate hashes to bypass refusal.

The existing preview/apply contract covers config/policy synchronization, selective
manifest changes and backups of changed original bytes. Both admission consumer
files are captured for the apply-time concurrent-edit check even when one or both
need no replacement. A runtime-only migration preserves config and policy bytes.
An admission-only patch does not reset gate observations: task and gate evidence,
deliberate waivers, learning history and unrelated contracts remain intact. Smoke,
video or delivery changes still follow their separate evidence-update rules.
Inspect backups and the complete manifest delta after applying; verify copied
gate and dashboard behavior using approved local checks.

The copied bundle does not acquire `admission_review.py` or a Run dispatcher.
The installed Run helper uses the installed admission assessor. Readiness reports
recorded policy and outstanding assessment needs; copying these helpers does not
verify permissions or billing, reserve capacity, enforce limits, refresh observations
or authorize scheduling. Keep policy adoption separate from those external actions.

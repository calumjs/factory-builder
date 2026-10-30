# Recovery: integrity, staged snapshots and worker health

Three situations, one stance: preserve what exists, review every delta, accept nothing wholesale, activate nothing automatically. The boundaries in the generated boundaries.md apply throughout.

## 1. Integrity recovery (manual procedure)

Use when hand-edited contracts or unregistered files block checks, status, gates or operations preview. Those refusals are intentional; recovery means a reviewed, selective manifest change, never accepting all current hashes.

**Baseline and backup**
1. Confirm the target and local-write authority. Stop writers and watchers only within their existing authority; if a stable snapshot cannot be obtained, stop. Back up the current factory — original manifest and every living record — to a private, untracked location outside `.software-factory`, recording paths, sizes and raw SHA256 before and after, and verify byte-for-byte. Do not follow links or copy secrets into a shared location.
2. Obtain an independently accepted baseline of this factory from a verified commit or verified backup, with its provenance and original manifest bytes. A newly generated factory, or a manifest from the same unreviewed edit, is not independent authority. Check the isolated baseline with the compatible trusted builder's `scaffold.py --check`.
3. Refuse legacy schema 1, unsafe or redirected paths, duplicate or ambiguous manifest entries, malformed UTF-8/JSON, or an unavailable baseline; resolve those separately. A historical baseline with another supported classification uses its compatible checker, not a guessed migration.

**Review**
4. In private scratch, diff baseline, current and proposed: full text per changed file, added/missing lists, old/new normalized hashes, original/proposed manifest, living-file changes. Compare config/policy controls semantically; a matching hash cannot approve new scope.
5. Classify every difference: restore unintended changes from the baseline (keeping the backup); retain useful customizations through the diff; move runtime notes, test maps and application/CI deliverables outside the factory, preserving references. A deliberately immutable new file may be registered as a **named contract** with rationale; never add a living directory or reclassify contracts. Schema 2 keeps exactly five living files.
6. Prepare the manifest diff for only the accepted changes using the trusted integrity module's normalized `digest`, not raw hashes and not `manifest_for` over the current tree. Keep deliberate optional rows WAIVED; never promote observations or reset living records to make recovery green.
7. Review the whole diff — custom instructions, config/policy agreement, provenance, backup and recovery paths — through the repository's normal review, recording reviewer, verdict and immutable revision. A review of an older diff does not cover a changed one. This manual path issues no `--approve-plan` digest; do not reuse an operations-update digest.

**Apply**
8. Immediately before writing, re-compare current paths and raw hashes (manifest and living files included) with the reviewed snapshot; any new edit needs a fresh review. Write contract changes first and the manifest last under a stable writer boundary. This is not atomic: on interruption, stop, preserve partial files, and restore the affected originals plus manifest together from the backup, or finish a newly reviewed recovery. Never overwrite concurrent edits or delete files/locks blindly.
9. Run integrity with the trusted helper, then validate config/policy controls, task-plan structure and gate rows, then assess the required stage for its actual subject. Only after integrity passes may `update_operations.py` produce a new preview; recovery and preference changes stay separate reviewed changes. Recovered hashes are not application evidence.

For future contract edits, include the selective manifest diff in the same reviewed change. Do not bypass broken helpers by fabricating living evidence.

## 2. Staged recovery helper

`scripts/recover_factory.py` automates the audit, selective manifest proposal, verified backup and creation of a **new** recovered snapshot. It never edits either input, activates a factory, starts or stops writers, or runs project code. The damaged factory stays blocked until a separate coordinated adoption using section 1.

**Supported boundary.** Schema 2 only; UTF-8 text; the five living files; current eleven-column gate rows; required core files present; consistent config/policy controls; current manifest semantically matching the pinned baseline manifest. Manifest edits, core deletion, malformed state, unsupported formats or conflicting policy need the manual procedure. Valid NOT RUN/FAILED/WAIVED records are preserved. Limits: 512 files, 512 directories, 1024 entries, depth 20, 256 KiB per file, 8 MiB total; links, junctions, device/unsafe/ambiguous-case paths and duplicate or non-finite JSON are refused. There is no secret redactor: keep inputs, diffs and backups private and do not use this path for artifacts holding credentials. It is a file-content snapshot, not an ACL or alternate-stream backup: inputs keep their permissions, new output inherits its approved private parent, and filesystem metadata is reviewed during adoption.

Baseline and source must be separate, non-nested directories; output and backup must not exist and must lie outside both. `--stable-inputs` records the operator's assertion that inputs are not changing; it creates no lock. Repeated inventory and hash checks catch ordinary edits, not atomic snapshots or adversarial mutation. In-place activation race safety is outside the helper.

**Audit, decide, review.** Always run the trusted installed builder's copy, never a script from either input:

```sh
python scripts/recover_factory.py --factory <damaged-root> --baseline <accepted-root> --output <new-private-snapshot> \
  --baseline-manifest-sha256 <independent-raw-sha256> --baseline-reference "<verified-commit-or-backup-review>"
```

The audit prints full text deltas, added/removed directories, identities, raw hashes and living-file differences, with no writes. Supply the **raw original manifest SHA256 from the accepted source**, not a hash of the damaged manifest. Then write a private decisions JSON with exactly three groups, each naming exactly its detected delta set with a reason per path:

```json
{"accept_changed":[{"path":"policy.md","reason":"Reviewed project-specific rule; controls remain consistent"}],
 "register":[{"path":"design-note.md","reason":"Reviewed immutable contract, not an evolving runtime record"}],
 "remove":[{"path":"obsolete-note.md","reason":"Reviewed retirement of optional contract"}]}
```

No wildcard acceptance. The helper does not relocate or delete files or register a mutable evidence directory; move an evolving test map or operator log outside the factory as a separate action before the audit. Repeat the audit with `--decisions <file>` and inspect every full diff, the proposed manifest and the target/backup paths — a truncated tool view is not a review. Terminal control characters are escaped for display; the raw file hashes bind the original bytes. The printed plan digest binds all input content, identities, original manifest, baseline pin, decisions and exact output; any change requires a new preview.

**Apply and verify completion.** With the identical reviewed arguments plus `--decisions <file> --apply --stable-inputs --approve-plan <digest>`, the helper re-verifies inputs, creates an exclusive backup at `<output-parent>/.factory-recovery-backups/<digest>/source`, compares backup bytes, creates the output exclusively, copies current artifacts unchanged, and writes the revised manifest last with checked write progress and readback. Drift fails the run and preserves partial private artifacts.

Completion requires the backup's `COMPLETED.json` plus verification against the approved plan — a byte-valid manifest left by a killed process is **unconfirmed** even if `scaffold --check` passes:

```sh
python scripts/recover_factory.py --verify-output <snapshot> --backup <backup-directory> --plan-id <reviewed-digest>
```

Failure leaves the original intact and partial output preserved; there is no force, resume, cleanup or activation. Adoption is a separate reviewed change under a stable writer boundary: confirm the live original still matches the reviewed source, retain new edits, adopt only the accepted result with the manual procedure, then re-run integrity and the applicable gate assessment.

## 3. Worker health, bounded retries and fallback

Use the task's tool recipe and worker-handoff.md; pin a provider only when the project requires it. Identify any permitted fallback, its data boundary, output format and execution authority during intake or Plan — the primary worker being unavailable does not authorize an alternative.

At each checkpoint confirm from the actual run ID, state, logs, expected artifact and branch whether a commit, PR or artifact already exists before retrying or switching; reconcile an existing artifact first to avoid duplicate commits. An auth, permission or data-boundary rejection stops that action — no identity or security change, no tool switch to get around it.

`budget.max_repair_attempts`, `max_minutes`, `max_workers` and the cost limit cover the task including every retry and fallback; a fallback does not reset them. Before retrying, name the new hypothesis, timeout, expected artifact and verification. Fallback is permitted only when its provider, data egress, cost, paths and actions fit existing explicit scope; use an isolated checkout and make sure the primary worker cannot write the same files concurrently. Never terminate a run outside authority. Record which worker/run produced the final artifact, its revision and checks. If automatic pickup exists, use its authorized pause or kill switch rather than reconfiguring a watcher. For a laptop fallback follow the generated launch-guide.md, keeping work blocked and pickup paused through authorized controls while any trust decision is pending.

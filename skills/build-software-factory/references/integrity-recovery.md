# Reviewed integrity recovery for an existing factory

Use this when hand-edited contracts or unregistered files block checks, status,
gates or operations preview. Those refusals are intentional. PR #15 improves error
paths; it does not authorize accepting the changed files. For a supported pinned
baseline and stable inputs, [staged recovery automation](recovery-automation.md)
can produce a reviewed recovered copy plus verified backup. It never edits/activates
the damaged original; manual adoption and unsupported cases use the procedure below.

## Establish the baseline without losing work

1. Confirm the actual target and applicable local-write authority. Stop writers
   and watchers only within their existing authority; otherwise coordinate with
   the owner. If a stable snapshot cannot be obtained, stop recovery. Do not launch
   or change scheduling. Preserve the current factory in a private backup outside
   `.software-factory`, including its original manifest and every living record.
   Record exact file paths, sizes and raw-byte SHA256 before/after copying; verify
   the backup byte-for-byte. Do not follow links/junctions or copy secret content
   into a shared review location. Keep backup/recovery materials untracked.
2. Obtain a trustworthy, previously accepted baseline of **this factory** from a
   verified repository commit or verified backup. Record repository identity,
   baseline commit/backup provenance and the original manifest bytes. Inspect that
   source's review history; a newly generated factory or a manifest supplied by
   the same unreviewed edit is not independent authority. Check the isolated
   baseline with the compatible trusted builder's `scaffold.py --check`.
3. Refuse legacy schema 1, unsafe absolute/traversal/device paths, redirected paths,
   duplicate/ambiguous manifest entries, malformed UTF-8/JSON or an unavailable
   trusted baseline. Resolve these separately; never recover by accepting all
   current hashes. If a historical baseline uses another supported contract
   classification, use its compatible checker rather than guessing a migration.

## Review a readable, selective change

4. In approved private scratch, compare baseline, preserved current state and the
   proposed result: readable full text diffs for each changed config, policy,
   skill or artifact; added/missing file lists; old/new normalized contract hashes;
   and original/proposed manifest diff. Include living-file changes in review even
   though their content is unhashed. Compare config/policy controls and authority
   changes semantically; a matching hash alone cannot approve new scope.
5. Classify every difference explicitly. Restore an unintended change from the
   accepted baseline while preserving its backup. Retain a useful customization
   through the reviewed diff. Move runtime notes, test maps and application/CI
   deliverables outside the managed factory by default, preserving references and
   history. If a deliberately immutable new contract really belongs inside it,
   register that **named file only** as a contract and record the rationale. Do
   not add a living directory or reclassify contracts as mutable. Schema 2 keeps
   exactly its five living files: verification.md, task-plan.json, learning-log.md,
   release-handoff.md and tools.json. An evolving test map belongs outside it.
6. Prepare the narrow manifest diff for only accepted additions/removals/edits.
   Use the trusted integrity module's normalized `digest` for accepted contract
   bytes (UTF-8 BOM/line endings canonicalized), not raw-byte hashes. Preserve every
   unaffected entry and the living classification. Do not run `manifest_for` over
   the current tree or hand-rewrite all hashes. Requiredness choices remain the
   user's: keep deliberate optional rows as WAIVED, never promote observations to
   PASSED or reset living records merely to make recovery green.
7. Review the entire proposed diff against the accepted baseline, including
   custom instructions, config/policy agreement, provenance, exact backup and
   recovery paths. Record the reviewer/verdict and immutable revision of that diff
   in the repository's normal review process. A review of an older diff does not
   cover a changed proposal. This manual procedure issues no `--approve-plan`
   digest; do not reuse an operations-update digest for a broken source. The staged
   helper has its own full-content/target-bound plan and verified backup/completion
   protocol. Automated in-place activation remains unsupported.

## Apply and verify within the reviewed scope

8. Before writing, compare the current paths and raw-byte hashes with the reviewed
   snapshot, including the manifest and all living records. Any new/unexpected edit
   requires a fresh snapshot/diff/review. Apply only that reviewed change, with a
   stable writer boundary. Preserve backups; write contract/path changes first and
   the reviewed manifest last. This is not a multi-file atomic transaction. An
   interruption leaves integrity blocked: stop, preserve partial files, and restore
   affected originals plus their manifest together from the verified backup, or
   finish a newly reviewed recovery. Never overwrite concurrent edits or blindly
   delete files/locks. If exclusive coordination cannot be assured, do not apply.
9. Run integrity with the compatible trusted helper. Validate config and policy
   controls together, the living task-plan structure and gate rows, then assess
   the required stage for its actual subject revision/target. A nonzero result
   remains blocked; recovered hashes are not application evidence or permission.
   Only after integrity succeeds may `update_operations.py` produce a normal new
   preview. Recovery and operational preference changes are separate reviewed
   changes; preserve customizations and existing optional-gate choices.

For future contract edits, include the selective manifest diff in the same reviewed
change. Plan/Build own real application tests/CI paths outside the factory; Verify
checks records, Release records actual-target observations. A separately authorized
CI integration can enforce integrity/stage checks, but scaffolding enables no CI.
Do not bypass broken helpers by fabricating passing living evidence.

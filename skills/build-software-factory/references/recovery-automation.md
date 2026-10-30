# Reviewed staged recovery for #17/#18

`scripts/recover_factory.py` automates audit, a selective manifest proposal, verified
backup and creation of a **new recovered snapshot**. It never edits either input,
activates a factory, starts/stops writers, runs project code or performs application
checks. The damaged factory remains blocked until a separate coordinated adoption.
This bounded path complements [manual recovery](integrity-recovery.md); it is not
an in-place force-rebaseline or atomic live-directory switch.

## Trusted baseline and supported boundary

Obtain an independently accepted baseline of this factory from a verified commit
or private verified backup. Inspect its history/identity and retain the provenance
reference. Supply the **raw original manifest SHA256** from that accepted source,
not a newly computed hash of the damaged manifest passed off as prior acceptance.
The helper verifies that pin and baseline content/structure; it cannot authenticate
review history or turn an arbitrary reference string into authority.

Baseline/source must be separate non-nested directories; output must not exist and
must be outside both. The backup area must also be disjoint. Only known schema 2,
UTF-8 text artifacts, the existing five living files, current eleven-column gate
rows, required core files and consistent config/policy controls are supported.
Current manifest must semantically match the pinned accepted baseline manifest.
Changes to the manifest itself, core deletion, malformed state, unsupported formats
or conflicting policy require manual recovery. Valid NOT RUN/FAILED/WAIVED records
are preserved; checks need not pass merely to recover byte integrity.

Limits: 512 files, 512 directories, 1024 total entries, depth 20, 256 KiB per file and
8 MiB total text. Enumeration and reads are capped and drift-checked. Links/junctions/reparse points,
device/unsafe/ambiguous case paths and duplicate/non-finite JSON are refused.
There is no secret redactor: keep inputs, full diffs, snapshots and backups private;
do not use this path for factory artifacts containing credentials/sensitive records.
This is a file-content recovery snapshot, not a general filesystem/ACL/alternate-
stream backup. Inputs keep their permissions; new output inherits its approved
private parent. Review filesystem metadata separately during any manual adoption.

Coordinate stable input trees and an exclusive trusted output-parent boundary
before apply. If that cannot be established within existing authority, stop at
audit. `--stable-inputs` records that operator assertion; it creates no OS lock or
permission. Repeated inventory/identity/hash checks detect ordinary edits, not an
atomic point-in-time snapshot, ABA attacks or an adversarial namespace mutator.
Staged creation avoids overwriting source edits. In-place activation race safety
is explicitly outside this helper and remains a manual coordination requirement.

## Audit, classify, review

Use the trusted installed builder code, never a Python file from either input:

```sh
python scripts/recover_factory.py --factory <damaged-root> --baseline <accepted-root> --output <new-private-snapshot> --baseline-manifest-sha256 <independent-raw-sha256> --baseline-reference "<verified-commit-or-backup-review>"
```

Audit prints full text deltas, added/removed directories, source/baseline identities,
raw hashes and living-file differences as data, with no writes and no approval plan.
Prepare a private decisions JSON with exactly these groups:

```json
{"accept_changed":[{"path":"policy.md","reason":"Reviewed project-specific rule; controls remain consistent"}],"register":[{"path":"design-note.md","reason":"Reviewed immutable contract, not an evolving runtime record"}],"remove":[{"path":"obsolete-note.md","reason":"Reviewed retirement of optional contract"}]}
```

Each group must name **exactly** its detected delta set, with a reason per path.
No wildcard/all-current-hashes acceptance. Unaffected contract hashes and living
classification stay unchanged. An evolving test map, CI output or operator log
normally belongs outside the factory; move it only as a separate reviewed action
before this snapshot audit. The helper does not relocate/delete files or register a
mutable evidence directory. It copies current living bytes without restoring old
baseline observations, resetting flags or fabricating PASS.

Repeat audit with `--decisions <private-decisions.json>`. Inspect every full diff,
config/policy meaning, proposed manifest and target/backup path. Terminal control
characters are escaped for display; raw file hashes bind the original bytes. Save
the full preview in an approved private location when needed. A truncated tool view
is not a complete review. The plan digest binds all input content/identities,
original manifest, baseline pin/reference, explicit decisions and exact output.
Any source/baseline/output/decision change requires a new preview and review.

## Apply and verify completion

Within applicable local-write authority, repeat the identical reviewed arguments:

```text
--decisions <private-decisions.json> --apply --stable-inputs --approve-plan <digest>
```

The helper verifies inputs, creates an exclusive backup at
`<output-parent>/.factory-recovery-backups/<digest>/source`, compares backup bytes,
and records the pinned plan. It exclusively creates the output, copies current
artifacts unchanged, then writes only the selectively revised manifest last.
Checked write-progress/flush/readback handles partial/zero/error writes. Drift
causes failure, retaining partial/private artifacts without deleting user files.

Completion also requires the backup's `COMPLETED.json` plus current verification
against the approved plan. A process death can leave a byte-valid manifest before
that completion record: **such output remains unconfirmed/quarantined** even if
scaffold --check succeeds. No success log or manifest alone proves this recovery
finished. Verify before any adoption, and again if output/backup might have changed:

```sh
python scripts/recover_factory.py --verify-output <snapshot> --backup <backup-directory> --plan-id <reviewed-digest>
```

This checks the completion/pinned plan, original backup, recovered bytes, structure
and config/policy consistency. It attests no application result or human identity.
Failure leaves the original source intact and any partial snapshot/backup preserved;
no force/resume/cleanup or activation is attempted. Do not blindly delete/reuse a
failed destination or overwrite concurrent work. Preserve it for diagnosis and
review a fresh plan/output when appropriate.

Adoption is a separate reviewed change under a stable writer boundary. Verify that
the current original still matches the reviewed source, retain new edits, and use
the existing manual procedure to adopt only the accepted result. Do not blindly
replace a live directory. Re-run integrity and applicable gate assessment afterwards;
recovered hashes do not establish tested/released readiness. CI enforcement, a live
migration and stronger platform-specific in-place locking remain separate work.

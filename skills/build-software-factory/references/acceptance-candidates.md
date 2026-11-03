# Reviewed inactive acceptance candidates

`scripts/acceptance_candidate.py` adds an explicit materialization step around the
[pure acceptance planner](acceptance-planning.md). Its default remains a read-only
preview. Apply creates a new inactive candidate and a verified backup; it never
changes the original factory, registers its new hashes, runs project checks or
adopts a candidate into active use.

The same bounded request, independently accepted manifest pin/reference, supported
document/map shapes and append-only limits apply. Existing evidence, optional
gates, waivers, seed tasks, living events and custom bytes remain preserved. The
new criterion starts required, pre-merge and NOT RUN. This does not attest test
coverage, provenance, execution authority or application readiness.

## First review: candidate bytes and destination

Choose a new candidate directory under an existing approved parent, outside the
source factory. Its sibling `.factory-acceptance-backups` area must also be disjoint
from the source and candidate. Keep these artifacts outside active factory trees;
the helper does not change repository ignore rules or delete old attempts.

```text
python -B <trusted-builder>/scripts/acceptance_candidate.py --factory <factory> --request <request.json> --baseline-manifest-sha256 <independently-accepted-raw-sha256> --baseline-reference <provenance-reference> --output <new-inactive-candidate>
```

Review the complete JSON preview and escaped diffs as untrusted data. Its digest
binds the pure synchronization plan, all original files/directories/identities,
exact proposed bytes, original pin/reference, resolved output/backup paths and
stable parent identities. Parent device/inode/type are bound; parent modification
time is not, because creating the approved output changes it. Do not derive a new
pin from an unreviewed current manifest. The helper cannot independently establish
that a supplied pin or reference was accepted.

Coordinate all writers and keep the source and output parent stable. After review,
repeat the same command with:

```text
--apply --approve-plan <exact-candidate-preview-digest> --stable-inputs
```

There is no implicit apply, overwrite, resume, adoption or cleanup. Changed inputs,
requests, paths, parents or digest require a fresh preview. Exclusive output/backup
creation and repeated inventory checks protect ordinary coordinated use; they are
not an atomic filesystem snapshot or a transaction against adversarial writers.

Apply verifies a complete original-byte backup before creating the candidate. It
copies only the approved candidate overlay onto those bytes, preserving directories
and the original manifest. **The original manifest is written last; the separately
predicted recovered manifest is never candidate content.** The candidate therefore
has intentional contract drift and cannot pass ordinary factory integrity yet.

The external backup directory is `<output-parent>/.factory-acceptance-backups/<digest>`.
It contains only `source/`, `candidate.json`, `decisions.json` and, after successful
checks, `COMPLETED.json`. No completion records or unregistered metadata are added
to a successful candidate. The source backup contains the original accepted scope;
the later recovery backup will contain the edited candidate. They are different
checkpoints and neither should be overwritten.

## Verify the candidate checkpoint

Successful apply prints actual literal `verify_argv` JSON arguments with the Python
interpreter, trusted helper, candidate, backup and approved plan identity. Execute
those arguments as a process argument array, without a shell. Equivalent CLI:

```text
python -B <trusted-builder>/scripts/acceptance_candidate.py --verify-output <candidate> --backup <candidate-backup> --plan-id <approved-candidate-digest>
```

Verification requires the externally retained digest and explicit roots. It checks
strict bounded metadata, its fixed file inventory, original backup bytes and pin,
reproducible synchronization, the full candidate inventory, original-manifest
identity and completion. It does not trust `backup_verified` or completion flags
alone, follow source paths supplied only by metadata, or require the active original
to remain unchanged forever. A later original edit remains authoritative and must
be reconciled before any separately authorized adoption.

Failure preserves the original and all available backup/partial output. If the
process still owns the same nonredirected candidate directory, it attempts to add
the reserved `RECOVERY-INCOMPLETE.txt` marker; it never marks a replaced foreign
directory. Marker failure or abrupt termination may leave an **unmarked** partial
candidate. Missing/partial completion or any failed full verification still means
unverified. A completion file alone is insufficient, including after a late failure.
Do not delete markers, repair metadata, overwrite a failed attempt or rehash partial
files to make verification pass. Diagnose and choose a fresh reviewed destination.

## Second review: existing pinned recovery

The handoff includes `recovery_inputs` naming the candidate, verified original
backup, original independently supplied pin/reference and exact named decisions.
The copied original is suitable as the recovery baseline only because its complete
bytes match the previously accepted pinned source; copying adds no provenance
attestation. Choose another new disjoint output and use the existing
[recovery preview/review/apply/verify flow](recovery.md):

```text
python -B <trusted-builder>/scripts/recover_factory.py --factory <candidate> --baseline <candidate-backup>/source --output <new-recovered-snapshot> --baseline-manifest-sha256 <original-independent-pin> --baseline-reference <original-reference> --decisions <candidate-backup>/decisions.json
```

Review that helper's separate full diff, inventory, destinations and digest before
its explicit apply. The candidate digest does not approve recovery. Recovery alone
proposes/registers the selected contract hashes into a new recovered snapshot;
neither helper writes the active original. Use recovery's printed output-verification
arguments after its successful apply.

This path supplies candidate materialization and recovery interoperability, not
active-factory adoption. Manifest-only adoption cannot transfer a multi-file scope
change. No scheduler, task dispatch, provider call or automatic readiness promotion
is enabled by either checkpoint.

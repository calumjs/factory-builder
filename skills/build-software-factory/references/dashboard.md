# Dashboard

Every factory gets `dashboard/index.html` plus a stdlib refresh helper: a self-contained, read-only page with no server, scripts, network or credentials, in light or dark mode. It renders the six-phase flow with derived counts, task progress, the required-gate ring and pills, work items, gates and waivers, factory passes from `.factory-runs/` where secure no-follow reads are supported, recent evidence events, and collapsed details (intake design, assumptions, workers, observations, provenance). Every value is a recorded claim with its freshness. The default overview does not assess a selected subject; an optional explicit full-stage assessment delegates to `gates.py`.

## Fit the project

Ask who operates the factory and which decisions the overview should support, then adapt: a library may want artifact validation and release candidates, a pipeline backlog and freshness, a web service deployment confirmation. Use only available records; task counts imply no health, throughput, spend or heartbeat. Optional `dashboard` config:

```json
{"title":"Library delivery overview","audience":"Package maintainers","work_item_label":"Package work","stale_after_minutes":120}
```

Labels are non-secret text (1–200 characters); freshness is 1–10080 minutes. Changing the profile later is a narrow reviewed config/manifest diff, not an operations patch.

## Refresh and integrate

```sh
python .software-factory/dashboard/dashboard.py --output factory-overview.html [--replace]
python .software-factory/dashboard/dashboard.py --output factory-overview.json --format json
python .software-factory/dashboard/dashboard.py --output factory-overview.html --observations <approved-metrics.json>
```

Output must be outside the factory. A failed refresh exits nonzero and leaves old output untouched; snapshots carry captured and expiry times and never refresh themselves.

The version-1 JSON DTO has `profile`, `captured_at`, `expires_at`, `mode`, `integrity`, `errors`, `sources`, `context`, `counts`, `tasks`, `workers`, `gates`, `release`, `events` (latest 30), `runs` (latest 20), `metrics`, `usage`. Missing expected gates are data errors; invalid structure, duplicates or failed integrity refuse the refresh. An existing project UI can consume the DTO, but must keep the freshness and WAIVED semantics and avoid raw HTML injection; hosting, authentication, external reads and operational controls are separate scope.

### Explicit subject assessment

```text
python .software-factory/dashboard/dashboard.py --output selected-overview.html --assessment-subject <exact-tested-subject> --assessment-stage pre-merge --assessment-reason "Checks ran on this reviewed subject; records were stored later."
```

Supply subject, stage and a non-secret operator explanation together. An optional
`--assessment-target <actual-observed-target>` is separate from planned deployment
configuration. Missing required post-merge target stays BLOCKED; a planned or
recorded target is never substituted. Subjects are exact strings, with no Git/HEAD
lookup, prefix expansion, equal-tree equivalence or evidence transfer. Use separate
snapshots when pre-merge and post-merge subjects differ; follow
[merge-subject-evidence.md](merge-subject-evidence.md) to distinguish tested and
record-storage identities.

Opt-in snapshots add `assessment` with the supplied `subject`, `stage`,
`actual_target` (null if omitted), `reason`, full-stage `scope`, `state`
(`blocked`/`satisfied`), `problems`, `omitted_problem_count`, `waived` and `notice`.
No-selection DTOs, counts and source lists remain unchanged. The same gate checker
retains global expected-row/stage checks and waiver semantics; an all-waived stage
may satisfy record rules while its rows still display WAIVED and their original
failed or unrun result. Nothing becomes a new PASSED observation. Diagnostics are
bounded to 100 messages. A longer message keeps a 600-character prefix plus the
fixed ` [diagnostic truncated]` suffix (623 characters total); truncation cannot
turn a blocked result into success. Observation-age labels remain separate
from exact-subject gate rules.

The chosen context is supplied data, not independently verified provenance, live
delivery, admission authority or proof that tests ran. Selected snapshots also bind
the policy bytes into the ordinary before/after read checks. Drift refuses output;
these checks are not an atomic filesystem snapshot. No evidence paths are followed.

Project metrics come from an adapter built in the project's own stack, outside the factory, writing a non-secret observations file (schema in the generated `dashboard/README.md`: ≤ 50 rows; statuses measured/unavailable/proposed/error; only measured carries a finite number; every row has a source label and a timezone timestamp). The helper never discovers or fetches sources.

## Privacy and rendering

The DTO carries task IDs, owner labels, revisions, run identifiers and supplied metric labels; it excludes run notes, goals, commands, evidence bodies, recorded target URLs, budgets, handoff prose, assumption text and sources (only position, status and blocker count appear). Explicit assessment subject, actual target and explanation are also exported when supplied: use only approved non-secret text (limits: 200, 2048 and 500 characters respectively, single-line without edge whitespace). Recorded/planned targets and raw exceptions are not added to the assessment output. Evidence paths are never followed. Sanitize identifiers at source and keep snapshots and adapter inputs untracked; escaping is not redaction. All values render as escaped text under a CSP of `default-src 'none'` with inline styles only ([CSP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy), read 2026-10-30).

## Adding the dashboard to an existing factory

`scripts/add_dashboard.py --factory <root>` checks schema-2 integrity and prints the generated bundle and hashes without writing; repeat with `--apply --approve-plan <digest>` within local-write authority. The digest binds every current factory file and bundle byte; drift, concurrent edits or an existing dashboard are refused, and only the new dashboard contracts and manifest entries are added. The original manifest is backed up under `.factory-update-backups/`. Writes are not atomic: on interruption, preserve the partial files and backup, inspect the diff, then restore the original manifest and remove only the reviewed partial additions, or finish a newly reviewed recovery. Schema 1 needs its own migration. For known older dashboards, `update_operations.py`'s runtime flags migrate the bundled code ([existing-factory-update.md](existing-factory-update.md)).

Windows run-history reads support local fixed, removable and RAM drives through retained no-reparse handles. UNC, network drives, unsupported filesystems and sharing conflicts are reported as unavailable rather than empty. Concurrent mapped writes are not an atomic snapshot, and bounded record sizes do not impose an I/O timeout. Records remain operator-supplied claims and run notes are excluded.

Existing copied dashboards keep their old behavior until reviewed migration. The
trusted installed helper can produce an explicit assessment without modifying the
factory. To upgrade supported copied code, preview `update_operations.py --factory
<root> --context-runtime --gate-runtime`, review the exact diff/digest, then use its
existing explicit apply mechanism. Context-only migration refuses an older gate
backend rather than pairing the new panel with different assessment semantics.
Only known predecessor bytes migrate; custom dashboard/gate copies are preserved
and refused for manual review. Original bytes are backed up, and unrelated updates
preserve the known old dashboard. Existing copied README/index snapshots remain
unchanged; use this installed guidance and refresh explicitly after migration.

On a manifest file-set mismatch, the dashboard reports safe counts and flags unexpected dashboard bytecode without echoing arbitrary filenames. Run the trusted `scaffold.py --check` privately for named paths; preserve the evidence and use reviewed recovery rather than resetting hashes. Older copied dashboards retain their behavior until a separately reviewed runtime migration.

Existing projects may lack optional root ignore rules for `factory-overview.html`, `factory-overview.json` and `.factory-recovery-backups/`. Inspect the project's root ignore policy and manually merge only the applicable scoped entries; never overwrite that policy. These rules keep local snapshots and recovery backups out of Git, not out of factory integrity checks. Do not ignore arbitrary unexpected manifest files to make a check pass.

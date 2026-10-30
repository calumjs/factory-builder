# Dedicated project overview

Every new factory receives `dashboard/index.html`: an immediately openable initial
snapshot, plus a standalone Python refresh helper. It works offline without a
server, credentials, dependencies or web deployment. Read-only views cover work,
assignments, gates/waivers, G3 release claims, recent events, provenance and usage.

## Fit the project

Ask who operates the factory and which decisions the overview should support.
Inspect existing UI conventions and approved evidence sources. A CLI/library may
need artifact validation and release candidates; a data pipeline may need batch
backlog and freshness; a web service may need deployment confirmation. Use only
available records. Do not infer health, throughput, uptime, spending or worker
heartbeats from task counts. Reuse an existing UI through the JSON DTO where useful,
preserving the local fallback. A dashboard does not create a scheduler.

Optional `dashboard` config (older configs remain valid):

```json
{"title":"Library delivery overview","audience":"Package maintainers","work_item_label":"Package work","stale_after_minutes":120}
```

Labels are non-secret text of 1..200 characters. Freshness is an integer 1..10080
minutes. Later profile changes require a narrow reviewed config/manifest diff,
not an operations patch or silent rebaseline. Record operators, source mappings,
missing sources and extension work in the accepted design. Research applicable
stack/version, accessibility, safe rendering and data-boundary questions using
primary documentation. Adapt views rather than inventing universal metrics.

## Refresh and integrate

From the project root with verified Python 3.9+:

```sh
python .software-factory/dashboard/dashboard.py --output factory-overview.html
# Only when intentionally replacing the reviewed destination:
python .software-factory/dashboard/dashboard.py --output factory-overview.html --replace
python .software-factory/dashboard/dashboard.py --output factory-overview.json --format json
```

Check exit status and captured/expiry times. A failed refresh returns nonzero and
preserves old output; it cannot make old data current. Snapshots never refresh
themselves: compare expiry with the current time. File modification is not an
observation. Recorded PASSED is not a readiness verdict: use the gate checker for
the exact revision/target. Optional rows stay WAIVED with their original result.

Version-1 DTO fields: `profile`, `captured_at`, `expires_at`, `mode`, `integrity`,
`errors`, `sources`, `counts`, `tasks`, `workers`, `gates`, `release`, `events`,
`metrics`, `usage`. Tasks contain ID/state/owner. Workers contain assignment counts
and unavailable liveness. Gates contain ID/stage/required/state/recorded_result/
revision/observed_at. Events contain task/time/state/result/revision/freshness
(latest 30). Sources contain relative artifact name/SHA256/mtime/freshness. Missing
expected gates are data errors; invalid structure, duplicates and failed contract
integrity refuse refresh. This is diagnostic data, not action authority.

For project metrics, build an adapter outside the factory in the existing stack.
It reads only authorized data and writes a non-secret local observations file.
The helper never discovers or fetches sources. `--observations <file.json>` accepts:

```json
{"schema_version":1,"metrics":[{"name":"Build duration","value":12,"unit":"seconds","source":"Approved local build log","observed_at":"2026-01-01T00:00:00Z","status":"measured"}]}
```

At most 50 rows. Name/unit/source/observed_at/status are nonempty text up to 200
characters. Status is measured/unavailable/proposed/error. Only measured has a
finite numeric value; others use null. All rows need a timezone timestamp and
source label. Stale/future observations remain marked. Supplied measurements are
claims, not independently attested facts. Budget/usage needs a real approved source;
limits are not consumption. Unavailable/proposed are different from zero.

## Privacy and rendering

Four fixed artifacts supply the data: config, task plan, verification and research,
after integrity validation. Raw goals, evidence, commands, URLs and handoff prose
are excluded; evidence paths are never followed. IDs, owner labels, revisions and
metric labels/values can still be private. Sanitize them at source, inspect output
before sharing and keep snapshots/adapter files private through reviewed ignore
rules. Escaping is not secret redaction. No output is published automatically.

All values render as escaped text; no active data links, Markdown or scripts.
Restrictive CSP permits local inline styling only. Existing UI adapters must avoid
raw HTML injection and preserve provenance/freshness/waiver semantics. Hosting/auth,
external connections, schedules and operational buttons need separate authority.
Primary references: [HTML escaping](https://docs.python.org/3/library/html.html) and
[CSP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy)
(read 2026-10-30). CSP is defense in depth, not a privacy boundary.

## Narrow existing-factory adoption

Do not rescaffold. `scripts/add_dashboard.py --factory <root>` checks schema-2
integrity, prints generated HTML/docs and exact file hashes, and writes nothing.
Review bundled scripts and the preview; within existing local write authority,
repeat with `--apply --approve-plan <digest>`. The digest binds every current
factory file and added bundle bytes to the target. Drift, concurrent edits or an
existing dashboard are refused. Custom skills, config, policy, gate choices,
operations and living records stay unchanged. Only new dashboard contracts and
manifest entries are added. Schema 1 needs separate migration.

The original manifest is backed up outside the factory in `.factory-update-backups/`.
Writes are not a multi-file atomic transaction. Interrupted writes leave partial
files and blocked integrity: preserve those and the backup, inspect the exact diff,
then restore the original manifest and remove only reviewed partial additions, or
finish a newly reviewed recovery. Never blindly rebaseline. Runtime output and
adapter input must stay outside `.software-factory`; extra files inside fail
integrity. This follows PR #15's runtime-location direction without changing its
diagnostics implementation. Keep backups private/untracked.

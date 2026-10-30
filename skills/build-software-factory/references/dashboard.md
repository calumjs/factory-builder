# Dashboard

Every factory gets `dashboard/index.html` plus a stdlib refresh helper: a self-contained, read-only page with no server, scripts, network or credentials, in light or dark mode. It renders the six-phase flow with derived counts, task progress, the required-gate ring and pills, work items, gates and waivers, factory passes from `.factory-runs/`, recent evidence events, and collapsed details (intake design, assumptions, workers, observations, provenance). Every value is a recorded claim with its freshness; it computes no readiness — `gates.py` does that for one revision.

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

Project metrics come from an adapter built in the project's own stack, outside the factory, writing a non-secret observations file (schema in the generated `dashboard/README.md`: ≤ 50 rows; statuses measured/unavailable/proposed/error; only measured carries a finite number; every row has a source label and a timezone timestamp). The helper never discovers or fetches sources.

## Privacy and rendering

The DTO carries task IDs, owner labels, revisions, run notes and supplied metric labels; it excludes goals, commands, evidence bodies, URLs, budgets, handoff prose, assumption text and sources (only position, status and blocker count appear). Evidence paths are never followed. Sanitize identifiers at source and keep snapshots and adapter inputs untracked; escaping is not redaction. All values render as escaped text under a CSP of `default-src 'none'` with inline styles only ([CSP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy), read 2026-10-30).

## Adding the dashboard to an existing factory

`scripts/add_dashboard.py --factory <root>` checks schema-2 integrity and prints the generated bundle and hashes without writing; repeat with `--apply --approve-plan <digest>` within local-write authority. The digest binds every current factory file and bundle byte; drift, concurrent edits or an existing dashboard are refused, and only the new dashboard contracts and manifest entries are added. The original manifest is backed up under `.factory-update-backups/`. Writes are not atomic: on interruption, preserve the partial files and backup, inspect the diff, then restore the original manifest and remove only the reviewed partial additions, or finish a newly reviewed recovery. Schema 1 needs its own migration. For known older dashboards, `update_operations.py`'s runtime flags migrate the bundled code ([existing-factory-update.md](existing-factory-update.md)).

"""Render the self-contained read-only overview bundle for new or existing factories."""
from pathlib import Path
from dashboard import page, summarize


def bundle(files):
    scripts = Path(__file__).resolve().parent
    result = {'dashboard/'+name: (scripts/name).read_text(encoding='utf-8')
              for name in ('dashboard.py', 'integrity.py', 'gates.py', 'operations.py', 'recipes.py','assumptions.py','readiness.py','learning_table.py')}
    result['dashboard/index.html'] = page(summarize(files))
    result['dashboard/README.md'] = '''# Local factory overview

`index.html` is the initial snapshot; it never refreshes itself. Refresh from the
project root to a file outside the factory:

    python .software-factory/dashboard/dashboard.py --output factory-overview.html
    python .software-factory/dashboard/dashboard.py --output factory-overview.json --format json

Add `--replace` to overwrite a previous snapshot. The page is self-contained:
no server, dependencies, network, credentials or scripts, and it adapts to light
and dark mode. It reads config, task plan, verification, research and the run
records in `../.factory-runs/` where secure no-follow reads are supported. Windows
uses handle-relative reads on local drives; unsupported paths or sharing conflicts
are explicitly reported. Integrity errors refuse the refresh.

What it shows: the six-phase flow with derived counts, task progress, the
required-gate ring and gate pills, work items, gates and waivers, factory passes,
recent evidence events, and collapsed details for intake design, assumptions,
workers, observations and artifact provenance. Every value is a recorded claim
with its freshness; WAIVED keeps its result and is never counted as passed, and
readiness for a specific revision still comes from `gates.py`.

An optional full-stage record assessment delegates to that same checker:

    python .software-factory/dashboard/dashboard.py --output selected-overview.html --assessment-subject <exact-tested-subject> --assessment-stage pre-merge --assessment-reason "Checks ran on this reviewed subject; records were stored later."

Subject, stage and explanation are required together. For post-merge confirmation,
also supply the separately observed `--assessment-target <actual-target>` when
required; no planned target or HEAD is inferred. The selected panel evaluates
record rules, not provenance, live delivery, admission authority or test execution.
Default snapshots retain their existing recorded-state overview without assessment.

Project metrics: pass `--observations <file.json>` (outside the factory) with
`{"schema_version":1,"metrics":[{"name":"Build duration","value":12,"unit":"seconds","source":"approved local build log","observed_at":"2026-01-01T00:00:00Z","status":"measured"}]}`.
Statuses are measured, unavailable, proposed or error; only measured carries a
number. Budget usage needs a measured source; configured limits are not spending.

Privacy: the HTML and JSON contain task IDs, owner labels, revisions, run identifiers
and supplied metric labels, but no run notes, goals, commands, evidence bodies, recorded target URLs,
budgets, handoff prose or credentials. Escaping is not redaction, so sanitize
those fields at source and keep snapshots and adapter inputs untracked. An
existing UI that consumes the JSON must keep the freshness and WAIVED semantics.
Explicit assessment subject/actual target/explanation are also exported when chosen;
supply only approved non-secret text. No recorded target/evidence is copied into that panel.
'''
    return result

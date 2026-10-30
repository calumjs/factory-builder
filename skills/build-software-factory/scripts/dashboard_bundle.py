"""Render the self-contained read-only overview bundle for new or existing factories."""
from pathlib import Path
from dashboard import page, summarize


def bundle(files):
    scripts = Path(__file__).resolve().parent
    result = {'dashboard/'+name: (scripts/name).read_text(encoding='utf-8')
              for name in ('dashboard.py', 'integrity.py', 'gates.py', 'operations.py')}
    result['dashboard/index.html'] = page(summarize(files))
    result['dashboard/README.md'] = '''# Local factory overview

Open index.html for the initial proposed snapshot. It does not refresh itself.
Refresh from the project root with a verified Python 3.9+ interpreter:

    python .software-factory/dashboard/dashboard.py --output factory-overview.html

Open factory-overview.html in a browser. Repeat with --replace only when overwriting
that snapshot is intended. Runtime output must stay outside .software-factory;
the dashboard source and initial snapshot are manifest-checked contracts.
No dependencies, credentials, server, network calls, worker or scheduler required.
Use --format json for a versioned DTO suitable for an existing project UI.
The generated bundle sets dont_write_bytecode before imports to avoid cache files.

Records are claims, not live activity or attested test results. Missing/malformed
sources fail with nonzero status; an old output remains old, never a fresh success.
Check command status and captured/expiry times. File modification is not observation.
Read-only assignments do not prove worker liveness. WAIVED does not mean PASSED.
The view does not compute release readiness; use gates.py for a specific revision.

Project-specific extension: pass --observations an explicitly approved local JSON
file outside the factory. Schema: {"schema_version":1,"metrics":[{"name":"Build
duration","value":12,"unit":"seconds","source":"approved local build log",
"observed_at":"2026-01-01T00:00:00Z","status":"measured"}]} (single-line name).
Statuses: measured, unavailable, proposed, error; only measured has a finite numeric
value, other statuses require null. Every row needs source and timezone timestamp.
No automatic source discovery/fetching. Budget/usage needs a real measurement;
configured limits are not consumption. Keep adapter inputs private and untracked.

The HTML/JSON allowlist excludes raw goals, check commands, evidence bodies, target
URLs, config budget, handoff prose and credentials. It includes task IDs, owner
labels, revisions and explicitly supplied metric labels/values. Sanitize these
before recording; escaping is not secret redaction. Snapshot files may still be
private: inspect before sharing, ignore runtime output, never publish automatically.
All user values render as escaped text with no active links, Markdown or scripts.
Existing UI integration must maintain this boundary, freshness and WAIVED semantics;
authentication/hosting, external reads and operational controls need separate scope.
'''
    return result

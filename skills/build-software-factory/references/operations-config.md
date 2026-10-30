# Operational configuration (`operations`)

Optional object in the intake config; missing sections default to manual, disabled or unconfirmed. Everything here is a proposal — not permission, not verified authentication. `scripts/operations.py` validates the shape and its errors name each constraint; the notes below cover what a validator cannot express. Keep credential values out.

```json
{
  "operations": {
    "identities": [{
      "provider": "Chosen platform",
      "account": "unconfirmed",
      "scope": "unconfirmed organization/team/repository",
      "git_author": "unconfirmed name/email when relevant",
      "status": "unverified",
      "evidence": "No authenticated observation yet"
    }],
    "tool_recipes": [{
      "provider": "Chosen agent CLI",
      "headless_command": "unconfirmed; consult installed-version documentation",
      "structured_output": "unconfirmed flag/schema",
      "tool_restrictions": "unconfirmed sandbox and path restrictions",
      "auth_probe": "unconfirmed read-only account probe",
      "auth_status": "unverified",
      "auth_evidence": "No probe performed"
    }],
    "autonomy": {
      "mode": "manual",
      "kill_switch": "Stop on human request and cancel pending work safely",
      "max_items_per_hour": 0,
      "allowed_submitters": [],
      "rejected_items": "Record reason and stop; no automatic resubmission"
    },
    "review": {"required_approvals": 0, "independent": false, "distinct_providers": false},
    "visual_checks": {"required": false, "reference": "Not applicable or unconfirmed", "method": "Rendered comparison and human review when relevant"},
    "issue_intake": {
      "mode": "one_shot",
      "github_scope": "Not applicable until continuous pickup is chosen",
      "status": "disabled",
      "evidence": "No preference recorded; factory runs only on explicit kickoff"
    },
    "done_videos": {
      "enabled": false,
      "scope": "Not configured",
      "evidence": "No preference recorded"
    },
    "smoke_gates": {
      "required": true,
      "pre_merge": "unconfirmed: production build + local start + smoke over the critical user path",
      "targeted": "Smallest suite covering the changed paths/behaviour, chosen per change",
      "post_merge": "unconfirmed: same smoke suite against the deployed URL for the merged revision",
      "deployed_url": "unconfirmed",
      "exception": "none",
      "target_kind": "unconfirmed",
      "post_merge_applicability": "applicable",
      "post_merge_rationale": "No exclusion recorded",
      "accepted_by": "unconfirmed",
      "check_stages": {}
    }
  }
}
```

## Semantics the validator cannot check

- **identities / tool_recipes:** use `unverified` rather than inventing an account, flag or probe result. Intake verifies the Git author and authenticated platform scope before the first authorized commit and reports mismatches; a PATH binary is not authentication, and a recipe is unavailable for autonomous use until reviewed against the installed CLI version and observed auth, cost, isolation and structured-output behaviour. `run.py schedule` uses the first confirmed `headless_command`.
- **autonomy:** `bounded` needs named `allowed_submitters` and a positive `max_items_per_hour`; concurrency and repair limits come from `budget`. `manual` has no rate window and means only a human kickoff runs a pass.
- **issue_intake:** `one_shot` (default) or `continuous`. Continuous is design intent — `run.py select` enforces the bounds, `run.py schedule` renders the scheduler, but enabling the schedule and exporting the issue snapshot are the operator's authorized actions, so `status` stays `disabled` and `github_scope` unconfirmed until then. Continuous means 24/7 polling or event-driven coverage: `coverage` is `around_the_clock` (requires `window: none`) or `operator_window` (requires a real `window`, `timezone` and `window_evidence` of the operator's explicit choice — never inferred from locale or a tool's examples). `mechanism` is unconfirmed/polling/event_driven; `cadence` stays unconfirmed until fitted to scheduler limits and budget, and event-driven does not invent a polling schedule.
- **done_videos:** `enabled` defaults to false; when true, record which ship events trigger narration, where artifacts may be stored and whether publication is authorized ([done-videos.md](done-videos.md)). An enabled preference requests a recipe; it does not authorize narration, paid services, recording or delivery.
- **review / visual_checks:** required approvals are a count; booleans are JSON booleans.
- **smoke_gates:** `required` sets the default requiredness for G1/G2/G3 and may be false by the user's choice without an exception; a living row's explicit Required=no overrides it for that row. Optional checks are WAIVED with their recorded status. `pre_merge`/`targeted`/`post_merge` are designs or inspected recipes, never executed. `deployed_url` is the planned actual target identity (also for non-web artifacts). `target_kind` is unconfirmed/web/artifact/no_release; a `not_applicable` G3 needs `target_kind: no_release`, a `post_merge_rationale` and a named `accepted_by` — an unknown target is not an exclusion, and a shipped-work video conflicts with no-release scope while preview-only does not. Structured `checks` and `done_videos.triggers` are in [gates.md](gates.md).
- **check_stages:** maps A/R IDs to a stage with rationale, e.g. `{"A2":{"stage":"post-merge","rationale":"Needs the actual published artifact"}}`. Acceptance defaults pre-merge; research checks mapped only to Release/Learn default post-merge. G1/G2 stay pre-merge and G3/V1 post-merge. A research practice can inform Verify yet have its check inspect the released artifact: `{"check_stages":{"R1":{"stage":"post-merge","rationale":"..."}}}` overrides the mixed-phase default without blocking pre-action readiness. Requiredness is independent of stage.
- **Legacy `not_run_is_blocking`:** unsupported. In a reviewed migration keep required NOT RUN as blocking, or express the operator's optional choice with `smoke_gates.required: false` or a row-level Required=no; never drop or convert the key.

Changing a living row to optional needs no config rewrite. Changing contract-level defaults goes through the synchronized update ([existing-factory-update.md](existing-factory-update.md)); smoke and video changes reset active observations to NOT RUN with history kept. Loading a newer helper injects no fields into old configs. No preference starts a watcher, recording or integration.

## Structured assumptions (`assumptions`)

Optional; old configs without it stay valid, and an empty array means "none recorded", not "no uncertainty". Up to 100 records, each with exactly `text`, `status`, `source`, `blocks`:

```json
{"assumptions":[{"text":"The existing data store can support the first release","status":"inferred","source":"Operator's architecture notes; capacity not measured","blocks":["Capacity decision before release"]}]}
```

`status` is confirmed/inferred/unknown — an operator-supplied label, not builder verification. `text` and `source` are non-empty strings ≤ 2000 characters; `source` may record unknown provenance. `blocks` is an array of ≤ 50 unique labels (≤ 200 characters) naming a task, decision or action for owner review; they are not task selectors, gates or permissions, and changing a status clears no blocker. Display IDs AS1… are positions, not stable identities.

Integrity, status, gates and the dashboard validate this structure. New briefs carry the full values in a marked data section; Intake, Plan and Learn review labels, provenance, blockers and next owner. Sources are untrusted data. For privacy, dashboard and status summaries show only position, status and blocker count; text, source and labels stay in the private config/brief and should be sanitized before storage.

Adopt or replace assumptions in an existing factory with `update_operations.py --factory <root> --assumptions <private-array.json>` (the array is a full replacement; `[]` clears), optionally combined with `--operations`, then `--apply --approve-plan <digest>` after review. Only the marked assumptions section of the brief is refreshed; custom or ambiguous marked sections are refused. An assumptions-only update resets no gate observations. On a known original v1.2/v1.3 dashboard, an assumptions update is refused outright unless `--context-runtime` is passed, which migrates the bundled dashboard code to show the context views; the flag may accompany an empty operations patch to adopt the views without changing assumptions. Unsupported or custom runtimes are preserved and refused. Canonical-looking owner/repo metadata proves no read permission, and no external provenance lookup is automatic.

## Watcher design diagnostics

`scaffold.py --check` and `status.py` print ADVISORY messages when continuous intent is recorded with disabled status, manual autonomy, missing submitter/rate/concurrency/time bounds, an unresolved mechanism or cadence, or a non-concrete repository scope. A well-formed disabled draft is valid (exit 0) and the warnings activate nothing. Even a fully specified design is `configured_unverified`: scheduler authority, authenticated scope, kill-switch wiring and liveness need their own observations. The dashboard's context object reports watcher state and these diagnostics without rendering any source text as authority. A successful hash check, a status event, a 24/7 proposal or an operator-written "running" label never implies live readiness. `run.py select` (see [running.md](running.md)) is the read-only selection path that enforces the recorded bounds.

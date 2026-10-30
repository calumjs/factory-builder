# Optional operational configuration

Legacy `not_run_is_blocking` is unsupported: do not copy it into operations. In a
reviewed migration, retain required NOT RUN checks as blocking, or express the
user's deliberate optional choice with `smoke_gates.required:false` (G1/G2/G3
defaults) or Required=no in a specific living row. Preserve the original record
and context; never silently drop an unknown legacy field or translate it to PASSED.
There is one requiredness system, with transparent WAIVED outcomes.

`operations` is an optional object in the intake config. Missing sections use manual, disabled or unconfirmed defaults. These are proposals, not permission or verified authentication. The helper validates and copies metadata; it runs no recipe, probe, agent or identity-changing command.

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

Each identity and recipe record uses exactly the shown fields, with nonempty strings. Use `unverified` rather than inventing an account, flag or probe result. Keep credential values out. Autonomous `mode: bounded` requires a positive integer rate limit and named permitted submitters; concurrency and repair limits come from `budget`. Required reviewer approvals are a non-negative integer. Review and visual booleans must be actual JSON booleans.

`issue_intake.mode` is `one_shot` (default) or `continuous`. Continuous mode is a design intent only until a watcher or scheduled routine is implemented with bounded `autonomy`, verified GitHub read scope and an authorized scheduler; record `github_scope` and `status` as unconfirmed/disabled until then. `done_videos.enabled` defaults to false; when true, record which ship events trigger narration, where artifacts may be stored and whether publication is authorized.

Continuous intent means **24/7 polling or event-driven intake**, not a weekday or
business-hours default. A time window is opt-in only. Optional flat issue_intake
fields are `coverage` (around_the_clock default, or operator_window), `mechanism`
(unconfirmed/polling/event_driven), `cadence`, `timezone`, `window`, `window_evidence`.
All text must be nonempty and at most 2000 characters. Around-the-clock requires
window=none. An operator_window needs a real window, timezone and evidence of the
operator's choice. Verify the timezone/cadence with the actual scheduler before any
authorized live action; the helper validates metadata, not cron syntax, IANA timezone
availability or runtime coverage. Cadence remains unconfirmed until fitted to platform
limits and budget. Event-driven does not invent a polling schedule. Unknown controls
remain a valid disabled draft and activate nothing.

```json
{"issue_intake":{"mode":"continuous","status":"disabled","evidence":"Operator chose continuous intake; scheduling authority pending","coverage":"around_the_clock","mechanism":"polling","cadence":"Operator-selected interval within scheduler limits","timezone":"UTC","window":"none","window_evidence":"none"}}
```

An explicitly selected restricted window uses coverage=operator_window plus its
window/timezone/source evidence; do not infer a window from business locale or a
tool skill's defaults. Existing live schedules are not changed by this metadata.
The marked proposed intake design in new policy files is refreshed by the reviewed
operations updater. Custom marked blocks are preserved/refused for manual review.
The normal config/policy controls remain authoritative; no new fields are injected
into old controls solely by loading a newer helper.

For composed video design and optional flat done_videos metadata, read
[done-videos.md](done-videos.md). Enabled preference requests a recipe; it does not
authorize narration, paid services, recording/data transfer or delivery messages.

Intake should verify existing Git author and authenticated platform account/scope when relevant before the first authorized commit or release. Report mismatches; do not silently change Git config, history, credentials, teams or security settings. A PATH binary alone is not available authentication. An authorized, harmless read-only probe is preferred; paid or mutating calls require their own authority. Recipes are unavailable for autonomous use until reviewed against the installed CLI version and observed authentication, cost, isolation and structured-output behavior.

`smoke_gates.required` sets the default requiredness for G1/G2/G3 and may be false by user choice without an exception or extra approval. Individual living verification rows may also explicitly use Required=no/n/false; this overrides the default for that row. Optional checks are visibly WAIVED with their recorded status, never tests-passed. Keep expected rows present: missing/malformed/duplicate rows are errors. The retained exception string is descriptive, not an authorization requirement. pre_merge/targeted/post_merge are designs or inspected recipes, never auto-executed commands. deployed_url is the planned actual target identity (also used for non-web artifacts); unconfirmed remains unresolved.

target_kind is unconfirmed, web, artifact or no_release. Post-merge applicability is applicable by default. A not_applicable G3 requires target_kind no_release, a specific post_merge_rationale and named accepted_by. An unknown target is not an exclusion. Enabled shipped-work videos conflict with a no-release exclusion and must be resolved explicitly.

check_stages optionally maps A/R IDs to a stage and nonempty rationale, e.g. {"A2":{"stage":"post-merge","rationale":"Needs the actual published artifact"}}. Unknown IDs are rejected. Acceptance defaults pre-merge; research checks mapped only to Release/Learn default post-merge, with explicit overrides available. Keep G1/G2 pre-merge and G3/V1 post-merge. Requiredness is independently user-editable and is not locked by these stage defaults.

A resource may inform Verify and Release while its observable check needs the
published artifact. For such a selected R1, set
`{"check_stages":{"R1":{"stage":"post-merge","rationale":"The practice informs Verify planning, but this check inspects the actual released artifact"}}}`
inside smoke_gates. This overrides the mixed-phase pre-merge default without a new
schema. Verify can plan it; future release evidence does not block pre-action
readiness. Keep checks that can run before release at pre-merge instead.

Changing a living row to optional needs no config rewrite, extra approval or exception. For changes to contract-level default preferences, use the normal synchronized config/policy/manifest update within existing local-write authority; this is integrity bookkeeping, not an extra approval for waiving a test. See [existing-factory-update.md](existing-factory-update.md). Smoke/video changes reset active observations to NOT RUN while retaining quoted history. No preference starts a watcher, recording or external integration.

When `issue_intake.mode` is `continuous`, wire pickup only after autonomy controls, issue filters and scheduler authority are confirmed; the scaffold does not start a watcher. When `done_videos.enabled` is true, respect the effective G3/V1 row requiredness: a required G3 passes before a required demo, an optional G3/V1 is explicitly WAIVED, and an optional demo is not required to exist. Keep recording, storage and upload within separately authorized data boundaries.

# Optional operational configuration

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
      "exception": "none"
    }
  }
}
```

Each identity and recipe record uses exactly the shown fields, with nonempty strings. Use `unverified` rather than inventing an account, flag or probe result. Keep credential values out. Autonomous `mode: bounded` requires a positive integer rate limit and named permitted submitters; concurrency and repair limits come from `budget`. Required reviewer approvals are a non-negative integer. Review and visual booleans must be actual JSON booleans.

`issue_intake.mode` is `one_shot` (default) or `continuous`. Continuous mode is a design intent only until a watcher or scheduled routine is implemented with bounded `autonomy`, verified GitHub read scope and an authorized scheduler; record `github_scope` and `status` as unconfirmed/disabled until then. `done_videos.enabled` defaults to false; when true, record which ship events trigger narration, where artifacts may be stored and whether publication is authorized.

Intake should verify existing Git author and authenticated platform account/scope when relevant before the first authorized commit or release. Report mismatches; do not silently change Git config, history, credentials, teams or security settings. A PATH binary alone is not available authentication. An authorized, harmless read-only probe is preferred; paid or mutating calls require their own authority. Recipes are unavailable for autonomous use until reviewed against the installed CLI version and observed authentication, cost, isolation and structured-output behavior.

`smoke_gates` describes the default G1 pre-merge local smoke, G2 change-targeted tests and G3 post-merge deployed smoke. `required` defaults to true; setting it false is refused unless `exception` records a human-accepted reason other than `none`. Commands are descriptions to inspect and authorize, never executed by the helper. Omitting the section keeps the required defaults.

When `issue_intake.mode` is `continuous`, wire pickup only after autonomy controls, issue filters and scheduler authority are confirmed; the scaffold does not start a watcher. When `done_videos.enabled` is true, run G3 post-merge smoke first and produce the demo only after it passes; treat narrated demos as release evidence in Verify/Release and keep storage or upload within approved data boundaries.

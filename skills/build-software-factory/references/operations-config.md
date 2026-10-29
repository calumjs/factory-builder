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
    "visual_checks": {"required": false, "reference": "Not applicable or unconfirmed", "method": "Rendered comparison and human review when relevant"}
  }
}
```

Each identity and recipe record uses exactly the shown fields, with nonempty strings. Use `unverified` rather than inventing an account, flag or probe result. Keep credential values out. Autonomous `mode: bounded` requires a positive integer rate limit and named permitted submitters; concurrency and repair limits come from `budget`. Required reviewer approvals are a non-negative integer. Review and visual booleans must be actual JSON booleans.

Intake should verify existing Git author and authenticated platform account/scope when relevant before the first authorized commit or release. Report mismatches; do not silently change Git config, history, credentials, teams or security settings. A PATH binary alone is not available authentication. An authorized, harmless read-only probe is preferred; paid or mutating calls require their own authority. Recipes are unavailable for autonomous use until reviewed against the installed CLI version and observed authentication, cost, isolation and structured-output behavior.

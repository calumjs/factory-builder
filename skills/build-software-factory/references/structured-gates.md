# Optional structured smoke recipes and video triggers

Old configs remain valid. No extra fields are injected into their policy controls.
Free-text pre_merge/targeted/post_merge remain designs when commands are not yet
inspected. There is one requiredness system: smoke_gates.required supplies smoke
defaults, and a living row's explicit Required=no/false is a user waiver. Neither
this schema nor an issue supplies execution/merge/deployment/narration authority.

## Smoke command, environment and target

Optional smoke_gates.checks maps G1/G2/G3 to exact records like this synthetic design:

```json
{"smoke_gates":{"checks":{"G1":{"command":["python","tests/smoke_cli.py"],"environment":"isolated installed-package fixture","env_names":[],"target":{"kind":"artifact","value":"synthetic-package-v1","base_url_env":null}},"G3":{"command":["python","tests/smoke_web.py"],"environment":"authorized released service","env_names":["BASE_URL"],"target":{"kind":"web","value":"https://fixture.example.invalid","base_url_env":"BASE_URL"}}}}}
```

This is an invented example, not a claim those commands exist. Select the project's
actual inspected commands, using a production-equivalent artifact and success/failure
assertions. command is 1..64 nonempty argv strings, each at most 2000 characters,
without controls. It is data, never a shell command the builder runs. environment
is a nonempty printable label without outer whitespace, line/control separators or
Markdown pipes; target values use the same representable form. env_names contains at most
64 unique variable names (no values, credentials or assignments). The checker reads
no environment variables and does not verify their presence or ownership.

target has exactly kind (web/artifact), value and base_url_env. Web value is a base
HTTP(S) URL without userinfo, query or fragment; base_url_env is null or a declared
env_names member. Artifact targets use null base_url_env and a meaningful package,
installed artifact or consumer identity. G3 structured target supplies the planned
target when old target_kind/deployed_url are unconfirmed; explicit conflicting old
values are rejected. A G3 command conflicts with an accepted no-release exclusion.

The generated row shows canonical argv/env-name design and environment label but
starts NOT RUN with blank actual target. For a still-required PASSED row, its design,
environment and target must match the configured recipe as well as the usual subject,
time, exit and evidence requirements. Operators must actually run/observe the
authorized procedure; a matching record proves no command ran. Configuring metadata
does not establish tool permissions, CI execution, env allowlists or application truth.
Changing recipes resets active observations through the synchronized updater; old
failures/waivers/history remain. Optional rows are WAIVED, never tests-passed.

Legacy not_run_is_blocking/blocking is not a second setting. Preserve required NOT
RUN as blocking, or the user's explicit optional row/default as WAIVED, during a
reviewed migration. Never silently drop an unknown legacy key or convert it to PASS.

## Explicit video triggers

Optional done_videos.triggers is a unique array containing pre_merge_preview,
post_g3_release, or both. Enabled videos need at least one selected trigger. When
omitted, enabled retains the old release-only behavior. Disabled creates no V rows.

- pre_merge_preview creates expected V2 at pre-merge for its actual local/preview subject.
- post_g3_release creates reserved V1 at post-merge for the shipped subject, after
  a still-required G3. A waived G3/V1 is disclosed and grants no media authority.

V2 cannot certify the V1/released subject. A missing/moved/duplicate expected row is
an error; each present row's intentional optional choice is respected. Do not parse
natural-language scope for trigger keywords. Explicit preview-only can coexist with
accepted no-release scope, whereas a release trigger cannot. Existing manually
added V2 rows stay extra checks unless the operator selects that structured trigger.
Removing a previously structured preview trigger retires its active row to quoted
history; unrelated manual V2 extras are preserved. Preference changes reset current
observations, preserve waivers, and never create video footage or PASS claims.

## Existing factories

Use update_operations.py's normal preview/digest/apply flow. New checks/triggers
need compatible copied dashboard operations/recipes/gates helpers. The explicit
--gate-runtime flag upgrades only known original v1.2–v1.5.1 sources and a known
missing v1.2 recipes dependency; custom/unknown code is refused and preserved.
Review code/config/policy/rows/manifest and verified backups together. It adds no
global install, CI job, watcher, command execution or live migration. Existing recipe
updates without these fields keep known compatible older helpers unless an explicit
runtime migration is selected. A plugin upgrade alone does not rewrite a factory.

# Scoped Claude Code phase discovery

## Pin the loaded source before choosing helper commands

Record the installed Claude version, plugin name/version/scope/status and actual
loaded plugin directory. Use `claude plugin list` or the installed-plugin details;
for --plugin-dir, inspect that exact directory's .claude-plugin/plugin.json. For a
Git checkout, record its full commit and dirty state with read-only Git inspection;
for an archive/cache, retain the verified source revision/checksum from its trusted
delivery record. A version string alone is not proof of a commit or untampered code.
Do not inspect credentials or assume the application's Git origin is the plugin source.

Resolve <trusted-skill-root> to skills/build-software-factory in that loaded source.
Before planning execution, inspect that root for scripts/scaffold.py, scripts/status.py,
scripts/gates.py and their imported local dependencies. The published v1.3 package
includes gates.py; an older package may not. A missing helper is a BLOCKED tooling
preflight, not a passing or notice-only CI gate. Do not invent a replacement engine,
guess a cache path or copy an isolated script with incompatible dependencies.

An installed-plugin update and a generated-factory migration are separate changes.
Within separately authorized install scope, update the verified plugin from its
trusted source and confirm the loaded version/path again in a fresh session (or
the installed version's supported reload). Cached/running sessions can retain old
code. Preserve existing factories; use the builder's narrow reviewed update when
their contracts/runtime need migration. While unavailable, retain actual manual
observations in living records and report automated assessment NOT RUN/BLOCKED.
Manual evidence is not a substitute for a still-required automated check. CI wiring
requires its own scope and an actual executable helper; no notice stub is enforcement.

## Human workspace trust and execution permissions

Before laptop fallback or headless work, have the human owner inspect the intended
checkout path, source, instructions/settings and project/plugin integrations. Where
Claude Code presents workspace trust, the owner decides in its normal interactive
UI for that directory. The agent must not accept it, edit trust state or select a
permission-bypass launch mode. A non-interactive session may show no trust prompt;
that absence does not prove the owner accepted trust or authorize using it as a
workaround. Trust is distinct from tool permissions, integration approval and task
authority; it grants no new deployment, data egress, spend or arbitrary execution.

Keep the affected task BLOCKED while required trust is pending. If automatic pickup
is already active, pause it only through its authorized control; otherwise ask the
owner to pause it. Do not start intake/fallback work to test around the barrier.
Record pending path/owner decision without sending messages outside authorized
scope. After the owner confirms the normal trust decision, recheck task permissions,
exact helper command and six-phase discovery below. A denied action remains denied.
Record worker/run identity, actual revision and outcome in the final handoff.

## Session-only phase loading

From the approved project root, after inspecting its settings/instructions, load the
trusted plugin for this session and retain the project setting source:

```sh
claude --plugin-dir "<trusted-plugin-root>" --add-dir .software-factory --setting-sources project
```

For an authorized headless read-only discovery pass, append:

```text
-p "Use /factory-intake for a read-only discovery/intake report. Do not edit files, run project commands, start workers or use external services. Stop if the actual skill is unavailable."
```

Check available commands/runtime skill metadata for factory-intake, factory-plan,
factory-build, factory-verify, factory-release and factory-learn at the intended directory. Before delivery,
verify an actual scoped phase Skill invocation succeeds; prose imitating a phase
does not establish discovery. A loaded builder plugin alone proves no phase load.

Empty --setting-sources removes the project source and can hide added-directory
skills. Bare/safe modes and managed customization policies have separate restrictions;
check installed-version help and policy. Current bare-mode docs allow explicitly
added-directory skills, so do not assume bare always disables them. If blocked,
report flags/version/path/policy and stop. Do not globally copy/install skills,
change settings, preapprove tools or bypass a policy to make discovery succeed.

This prompt is task scope, not a sandbox. Existing permissions/cost/data boundaries
apply. Before verification/release, record the selected existing interpreter's
absolute path and the exact trusted helper argv, target and subject. A Python
binary on PATH or a wrapper recipe does not establish permission to run that
selected executable. Check the task-specific policy for gates/status/evidence
commands before relying on them. If a dontAsk/allowlist rule blocks a helper,
report its exact command and pending action; obtain only the bounded task-specific
authority through the normal permission process. Keep evidence NOT RUN/BLOCKED.
Do not switch interpreters, wrappers or shell routes to evade denial, change global
permissions or treat consumer smoke as completed release confirmation.

Example command identity to review (substitute approved actual paths):

```json
["<existing-interpreter>","<trusted-skill-root>/scripts/gates.py","--factory","<factory-root>","--stage","pre-merge","--revision","<actual-subject>"]
```

Primary references (checked 2026-10-30):
[added-directory skills](https://code.claude.com/docs/en/skills#load-skills-from-a-directory-outside-the-project),
[CLI flags](https://code.claude.com/docs/en/cli-reference).
Version/update and trust references (read 2026-10-30):
[installed-plugin details and updates](https://code.claude.com/docs/en/discover-plugins),
[workspace trust and permissions](https://code.claude.com/docs/en/security).

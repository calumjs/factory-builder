# Scoped Claude Code phase discovery

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

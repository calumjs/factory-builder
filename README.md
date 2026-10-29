# Software Factory plugin

A Claude Code plugin with two reusable skills:

- `/software-factory:build-software-factory` asks adaptive questions, researches current task-specific practices, and scaffolds six phase skills: Intake, Plan, Build, Verify, Release and Learn.
- `/software-factory:contribute-upstream` captures reusable improvements, resolves the component's original repository, checks contribution policies and duplicates, and prepares issues or focused tested PRs within explicit publication authority.

The builder applies selected research practices as concrete instructions and planned checks in generated skills. It preserves source observations, compatibility and trade-offs. Blocked, stale or incomplete research remains an explicitly unresearched draft.

## Install from GitHub

This repository is private. The installing account needs repository access and working Git authentication.

In Claude Code:

```text
/plugin marketplace add calumjs/software-factory-plugin
/plugin install software-factory@software-factory-plugins
```

Then invoke either skill above. The marketplace and plugin use standard [Claude Code plugin packaging](https://code.claude.com/docs/en/plugins/create). No hooks, MCP servers, credential setup or permission-setting changes are bundled.

For a session-only local preview without installation:

```sh
claude --plugin-dir /path/to/software-factory-plugin
```

## Build a factory

Start with `/software-factory:build-software-factory` and describe the goal and intended local project. Intake reuses known answers and asks about scope, tools, identities, evidence, budget and autonomy only where relevant. Before generation, the skill researches relevant current primary sources using the host's available browsing tools.

After authorized local writes, the offline Python helper creates only `<project>/.software-factory/`. It creates six skills and operating artifacts; it does not implement the product, run workers or tests, enable providers, publish issues or deploy. It refuses existing output rather than overwriting it.

Start Claude from the project root with `claude --add-dir .software-factory`, then use `/factory-intake`, `/factory-plan`, `/factory-build`, `/factory-verify`, `/factory-release` and `/factory-learn`. Confirm additional-directory skill discovery under the installed version and organization policy. See the builder's [scaffolding guide](skills/build-software-factory/references/scaffolding.md) for helper commands and Windows interpreter selection.

Contract files are integrity-checked using normalized text hashes. Living task/evidence, verification, tools, release and learning records may evolve. The status helper records status and revision-bound evidence together without executing or attesting the check. Existing schema 1 factories require a reviewed migration.

## Improve reusable components

During authorized work, capture useful observations and use the contribution skill to prepare a sanitized draft. The upstream is resolved from the affected component's verified source, not automatically the current application's origin. Check actual upstream CONTRIBUTING, issue/PR and security policies, including restrictions on agent-authored PRs. Verify duplicate searches. Private project data and secrets stay out of contributions.

An issue, comment, fork, push or PR needs applicable explicit or bounded standing authorization. Installation, invocation and generated provenance provide none. No automatic watcher, schedule, PR approval or merge is created.

## Validate and test

Requires Claude Code with plugin support and Python 3.9+ for the helpers. They use only the standard library.

```sh
claude plugin validate . --strict
python -m unittest discover -s skills/build-software-factory/scripts -p "test_*.py" -v
```

Tests use isolated temporary folders and synthetic research records. They cover preservation, draft/research mapping, contract checks, living records, line endings, status/evidence updates, provenance and disabled command execution. They do not claim an application passed tests or that mock sources were browsed.

Stage explicit reviewed source paths. Keep credentials, caches, backups, local feedback and downstream factory outputs out of this plugin repository. Optional operating patterns and adoption decisions are recorded in [design decisions](docs/design-decisions.md).

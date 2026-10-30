# Software Factory plugin

A Claude Code plugin with two reusable skills:

- `/software-factory:build-software-factory` asks adaptive questions, researches current task-specific practices, and scaffolds six phase skills: Intake, Plan, Build, Verify, Release and Learn, plus `/factory-run`, the engine that selects work, dispatches bounded parallel workers through them and can be scheduled.
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

After authorized local writes, the offline Python helper creates only `<project>/.software-factory/`. It creates seven skills (six phases and the run engine) and operating artifacts; it does not implement the product, run workers or tests, enable providers, publish issues or deploy. It refuses existing output rather than overwriting it.

Start Claude from the project root with `claude --add-dir .software-factory`, then use `/factory-run` to drive a pass, or the phases individually: `/factory-intake`, `/factory-plan`, `/factory-build`, `/factory-verify`, `/factory-release` and `/factory-learn`. Confirm additional-directory skill discovery under the installed version and organization policy. See the builder's [scaffolding guide](skills/build-software-factory/references/scaffolding.md) for helper commands and Windows interpreter selection.

For isolated/headless phase discovery, keep `--setting-sources project` and follow the generated launch-guide.md preflight; an empty source list can hide phases. Risk-focused Verify guidance adapts independent review and identifier/persistence fault cases to the project's actual promises, preserving discovered failures and exact repair-revision evidence.

The launch guide also pins the actual loaded source/version, checks helper availability
and separates the human workspace-trust decision from execution permissions. New
factories include a task-fitted connection-string review guide: synthetic provenance
can justify a non-secret classification, while local hosts, fixture usernames and
documentation paths are never blanket exemptions. Check changes need fresh evidence;
no secret scanner, trust change or CI enforcement runs automatically.

Every generated factory requires production-equivalent local smoke (G1), change-targeted tests (G2) and applicable acceptance/research checks before pre-merge readiness. After a separately authorized release, G3 checks the actual web URL or installed/published artifact at the merged revision. Pending post-action evidence does not block pre-action readiness; it does prevent claiming the release confirmed. Required failed, NOT RUN, malformed, stale, removed or wrong-target evidence blocks its stage. The offline gate helper validates records only; build/hash success is not application verification. Enabled narrated videos have a post-G3 V1 handoff.

Existing factories can opt in through a [narrow reviewed update](skills/build-software-factory/references/existing-factory-update.md), preserving custom instructions and historical evidence.

Optional [structured smoke recipes and video triggers](skills/build-software-factory/references/structured-gates.md)
record argv, environment names and actual-target designs. Explicit preview/release
triggers create separate V2/V1 rows; omitted fields preserve older behavior. These
records run nothing. Known copied runtimes need an explicit reviewed upgrade before
new metadata is adopted; custom code and intentional waivers remain protected.

Broken schema-2 factories with a pinned accepted baseline can use [staged recovery](skills/build-software-factory/references/recovery-automation.md): audit named drift, approve a complete plan, and create a verified recovered copy and backup. The source stays untouched; completion verification and coordinated manual adoption remain separate from application verification or live activation.

Optional [structured assumptions and advisory watcher diagnostics](skills/build-software-factory/references/context-status.md) preserve recorded confirmed/inferred/unknown claims, provenance and blocker labels. Checks/status display sanitized summaries; continuous drafts receive nonblocking warnings without asserting a live or authorized watcher. Known older dashboards can adopt context views through a separate reviewed runtime migration.

Continuous intake means 24/7 polling/event-driven intent unless the operator explicitly selects a window; one-shot remains the default and no watcher is created. Enabled done videos receive a [composed genuine-footage recipe](skills/build-software-factory/references/done-videos.md) with script/shot planning, project-specific tools/branding, captions, provenance and inspected delivery. Remotion is optional; voice preference never supplies narration approval. Scaffolding records proposed metadata and generates no media or external messages.

New factories also receive a dedicated local read-only dashboard: open `.software-factory/dashboard/index.html`, then refresh with its bundled Python helper to an external snapshot. It shows actual recorded work, assignments, gates/waivers, release claims and provenance; missing live activity or usage stays unavailable. [Dashboard design and adoption](skills/build-software-factory/references/dashboard.md) covers project-specific profiles, existing-UI JSON integration and narrow opt-in for existing factories. No credentials, server, hosted stack or background process is required.

Contract files are integrity-checked using normalized text hashes. Living task/evidence, verification, tools, release and learning records may evolve. The status helper records status and revision-bound evidence together without executing or attesting the check. Existing schema 1 factories require a reviewed migration.

New factories receive an inactive [portable CI evidence job](skills/build-software-factory/assets/templates/ci/README.md).
Its trusted helper distinguishes tested S from storage E, constrains evidence-only
changes and checks required recorded gates/tasks. It executes no application tests
and installs no workflow; adopting it into project CI requires separate scope.

## Run a factory

`/factory-run` is the engine. One pass: the builder's `run.py select` checks integrity, the kill switch (`.factory-runs/STOP` or `FACTORY_STOP=1`), `budget.max_workers` minus in-progress tasks, the hourly rate window and dependencies, then `run.py plan` renders one worker prompt per eligible task. The session starts one subagent per worker (isolated worktree where available) to perform Build and Verify for a single task, waits, then performs Release and Learn once and records the pass in `.factory-runs/` outside the factory. Tasks with overlapping `allowed_paths` are never dispatched together.

Continuous operation needs `issue_intake.mode: continuous` and `autonomy.mode: bounded`. `run.py schedule --kind cron|launchd|windows|github` renders a definition from the recorded cadence (60-minute floor) and prints it; enabling it is the operator's separate action. Issue pickup reads a snapshot the scheduler job exports; the helper filters submitters, duplicates and dependencies and never labels, claims or comments. See the [running guide](skills/build-software-factory/references/running.md) and the generated `scheduling/README.md`.

## Improve reusable components

During authorized work, capture useful observations and use the contribution skill to prepare a sanitized draft. The upstream is resolved from the affected component's verified source, not automatically the current application's origin. Check actual upstream CONTRIBUTING, issue/PR and security policies, including restrictions on agent-authored PRs. Verify duplicate searches. Private project data and secrets stay out of contributions.

An issue, comment, fork, push or PR needs applicable explicit or bounded standing authorization. Installation, invocation and generated provenance provide none. No automatic watcher, schedule, PR approval or merge is created.

## Validate and test

Requires Claude Code with plugin support and Python 3.9+ for the helpers. They use only the standard library.

```sh
claude plugin validate . --strict
python -m unittest discover -s skills/build-software-factory/scripts -p "test_*.py" -v
```

Tests use isolated temporary folders and synthetic research records. They cover preservation, default delivery gates, draft/research mapping, contract checks, living records, line endings, status/evidence updates, provenance and disabled command execution. They do not claim an application passed tests or that mock sources were browsed.

Stage explicit reviewed source paths. Keep credentials, caches, backups, local feedback and downstream factory outputs out of this plugin repository. Optional operating patterns and adoption decisions are recorded in [design decisions](docs/design-decisions.md).

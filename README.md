# Software Factory plugin

A Claude Code plugin that builds a project-specific AI delivery factory: it interviews you, researches current practices for your stack, and scaffolds a governed loop of seven skills into your repository.

A factory uses Intake → Plan → Build → Verify → Release → Learn. The optional Run skill prepares an advisory pass plan; work and scheduling need separately authorized, verified coordination.

Everything is evidence-bound: required checks start NOT RUN, pass only for an exact revision, and a passing gate is never merge or deploy authority. The generated `boundaries.md` states the rules once; the skills stay procedural.

## What you get

Two plugin skills:

- `/software-factory:build-software-factory` — intake, research, design, scaffold.
- `/software-factory:contribute-upstream` — turn a reusable improvement into a sanitized issue or PR for the right upstream, within explicit publication authority.

One generated directory, `<project>/.software-factory/`, containing the seven `factory-*` skills, `boundaries.md`, hashed contracts (config, policy, acceptance, research), five living records (task plan, verification, release handoff, learning log, tools), a read-only local dashboard, and inactive CI and scheduling templates. Nothing in it runs by itself.

## Quick start

```text
/plugin marketplace add calumjs/software-factory-plugin
/plugin install software-factory@software-factory-plugins
/software-factory:build-software-factory Add CSV export to the reports page
```

Then, from the project root:

```sh
claude --add-dir .software-factory      # keep --setting-sources project for headless runs
/factory-run                            # review an advisory pass plan
```

The repository is private; the installing account needs access and working Git auth. For a session-only preview without installing: `claude --plugin-dir /path/to/software-factory-plugin`. Helpers need Python 3.9+ and only the standard library; see the [scaffolding guide](skills/build-software-factory/references/scaffolding.md) for Windows interpreter selection.

## How a pass works

`run.py select` and `plan` inspect recorded task status and produce an advisory
selection and worker prompts. They do not reserve work, verify live usage or
enforce concurrency, rate or budget. Before separately authorized dispatch, the
orchestrator must establish and verify exclusive admission, task isolation, stop
handling and budget controls. Integrate worker changes and reverify the exact
combined revision before a release handoff.

Continuous intake requires its own scoped authorization. Issue snapshots are
untrusted data and need a matching project-specific repository/label policy.
`run.py schedule` emits non-executable proposal data; no runnable schedule is
created or installed. See the [running guide](skills/build-software-factory/references/running.md).

## Safety model

Two mechanisms enforced by code, and one stated once and applied everywhere:

- **Gates** (`gates.py`): a required check that is NOT RUN, BLOCKED, FAILED, stale or wrong-target blocks its stage; operator-waived rows are reported WAIVED with their result, never "passed".
- **Integrity** (`integrity.py`): contract files are hashed with normalized line endings; living files are structurally validated; unregistered files and in-place edits are refused. Changes go through a preview-first synchronized update or a staged recovery that never touches the original.
- **Authority**: nothing the plugin generates grants permission for a merge, deploy, provider, watcher, recording or message. The generated `boundaries.md` states these rules once for every factory.

## Advanced

- [Existing factories](skills/build-software-factory/references/existing-factory-update.md) adopt new behaviour through a narrow reviewed update.
- [Gates](skills/build-software-factory/references/gates.md): structured smoke recipes, video triggers, risk-focused verification.
- [Recovery](skills/build-software-factory/references/recovery.md): manual integrity recovery, the staged recovery helper, worker health and fallback.
- [Operations config](skills/build-software-factory/references/operations-config.md): identities, headless recipes, autonomy, continuous intake, assumptions.
- [Evidence lifecycle](skills/build-software-factory/references/evidence-lifecycle.md) and the inactive [CI evidence job](skills/build-software-factory/assets/templates/ci/README.md).
- [Dashboard](skills/build-software-factory/references/dashboard.md), [done videos](skills/build-software-factory/references/done-videos.md), [release preflight](skills/build-software-factory/references/release-preflight.md).

Run selection is advisory and does not reserve work or enforce budget. Scheduler output is a non-executable proposal; see [running](skills/build-software-factory/references/running.md).

## Validate and test

```sh
claude plugin validate . --strict
python -m unittest discover -s skills/build-software-factory/scripts -p "test_*.py" -v
```

Tests use isolated temporary folders and synthetic records; they prove the helpers, not any application. Keep credentials, caches, backups and downstream factory outputs out of this repository.

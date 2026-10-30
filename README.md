# Software Factory plugin

A plugin that builds a project-specific AI delivery factory: it interviews you, researches current practices for your stack, and scaffolds a governed loop of seven skills into your repository. It ships as a Claude Code plugin; the factory it generates uses the open Agent Skills format and stdlib Python, so any harness that loads skills and has a subagent mechanism can run it.

```
                 ┌────────────────────────── /factory-run ──────────────────────────┐
                 │  select work · dispatch N workers · release · learn · record     │
                 └──┬──────────┬──────────┬──────────┬──────────┬──────────┬───────┘
                    ▼          ▼          ▼          ▼          ▼          ▼
                 Intake  →   Plan   →   Build  →  Verify  →  Release →  Learn
                 brief       tasks      one task   G1/G2     G3 on the   log,
                 + gates     + owners   per worker evidence  real target improve
```

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

Then load `.software-factory/.claude/skills/` in your harness as an additional skills directory and invoke `factory-run` for one pass (select → build/verify in parallel → release → learn). In Claude Code that is `claude --add-dir .software-factory` then `/factory-run`.

The repository is private; the installing account needs access and working Git auth. For a session-only preview without installing: `claude --plugin-dir /path/to/software-factory-plugin`. Helpers need Python 3.9+ and only the standard library; see the [scaffolding guide](skills/build-software-factory/references/scaffolding.md) for Windows interpreter selection.

## How a pass works

1. **Select.** `run.py select` checks integrity, the kill switch (`.factory-runs/STOP` or `FACTORY_STOP=1`), `budget.max_workers` minus in-progress tasks, the hourly rate window, and task dependencies. Tasks with overlapping `allowed_paths` are never dispatched together.
2. **Dispatch.** The harness starts one worker per eligible task with its own subagent mechanism, isolated where it can be; each performs `factory-build` then `factory-verify` and returns revision, checks run and evidence.
3. **Release and learn.** Once, for the pass. Readiness requires every still-required G1/G2 check to pass for the exact revision; G3 confirms the real URL or published artifact only after a separately authorized release.
4. **Record.** The pass is written to `.factory-runs/` outside the hashed directory.

Continuous operation (`issue_intake.mode: continuous` with `autonomy.mode: bounded`) adds `run.py schedule --kind cron|launchd|windows|github`, which renders a scheduler definition you review and enable yourself, and `select --issues snapshot.json`, which filters a read-only issue export. Details: [running guide](skills/build-software-factory/references/running.md).

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
- [Operation](skills/build-software-factory/references/operation.md): worker contract, evidence chain, first release of a target, continuous pickup; the inactive [CI evidence job](skills/build-software-factory/assets/templates/ci/README.md).
- [Dashboard](skills/build-software-factory/references/dashboard.md), [done videos](skills/build-software-factory/references/done-videos.md), [research record](skills/build-software-factory/references/research.md), [intake questions](skills/build-software-factory/references/intake.md).

## Validate and test

```sh
claude plugin validate . --strict
python -m unittest discover -s skills/build-software-factory/scripts -p "test_*.py" -v
```

Tests use isolated temporary folders and synthetic records; they prove the helpers, not any application. Keep credentials, caches, backups and downstream factory outputs out of this repository.

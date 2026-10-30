---
name: factory-run
description: Drive this project's software factory end to end. Select eligible work, dispatch Build and Verify to bounded parallel workers, then run Release and Learn, in one pass or on a schedule. Use when asked to run the factory, process the backlog, start a factory pass, or set up a scheduled run.
---

# Run

The engine for the six phases; it adds no authority they lack.

## 1. Select

```sh
python <builder-skill-dir>/scripts/run.py --factory <root> select
```

Read-only. It refuses on failed integrity, an active kill switch, exhausted budget or no capacity, and reports `mode`, `capacity` and `candidates`. The kill switch is a `STOP` file in the run directory (default `<project>/.factory-runs/`) or `FACTORY_STOP=1`; only the operator removes it. No candidates with blockers listed is a finished pass: report and stop.

## 2. Dispatch

```sh
python <builder-skill-dir>/scripts/run.py --factory <root> plan
```

One worker per candidate, up to `budget.max_workers`, each with a prompt rendered from worker-handoff.md. Start one worker per plan entry using your own subagent or worker mechanism, each in an isolated checkout where you have one, and wait for all of them. Each worker performs the `factory-build` then `factory-verify` skills for its single task and returns status, revision, checks run, evidence and blockers. Tasks with overlapping `allowed_paths` are never in the same plan. Do not add workers beyond the plan or reuse a worker for a second task in the same pass. A blocked or failed worker is recorded as such; retry only with a new hypothesis and within `budget.max_repair_attempts`.

## 3. Release and learn

After every worker returns, perform `factory-release` once for the pass, then `factory-learn` once. A READY handoff is still not merge or deploy authority.

## 4. Record

```sh
python <builder-skill-dir>/scripts/run.py --factory <root> record --run-id <id> --dispatched T1,T2 --outcome completed --notes "..." --apply
```

Run records live outside the factory directory; the rate limit, dashboard and next pass read them.

## Continuous operation

Loop passes in one session only when `issue_intake.mode` is `continuous`, `autonomy.mode` is `bounded` and the pass is within `budget.max_minutes`; re-run `select` between passes. For 24/7 coverage use a scheduler:

```sh
python <builder-skill-dir>/scripts/run.py --factory <root> schedule --kind cron|launchd|windows|github
```

It renders a definition from the recorded cadence and the headless recipe in `tools.json`, and installs nothing; review it and enable it within authorized scheduler scope (scheduling/README.md). Issue pickup uses a read-only snapshot exported by the scheduler job (`select --issues <snapshot.json>`); this skill never lists, labels or claims issues.

## Exit
Run ID, mode, workers dispatched, per-task status/revision/evidence, release handoff state and learn entry.

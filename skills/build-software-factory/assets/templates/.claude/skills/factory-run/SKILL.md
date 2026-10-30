---
name: factory-run
description: Drive this project's software factory end to end. Select eligible work, dispatch Build and Verify to bounded parallel workers, then run Release and Learn, in one pass or on a schedule. Use when asked to run the factory, process the backlog, start a factory pass, or set up a scheduled run.
---

# Run

This skill is the engine that drives the six phases; it adds no authority that the phases lack.

## 1. Preflight

Run the builder's run helper. It is read-only and refuses to proceed on a failed integrity check, an active kill switch, exhausted budget or capacity:

```sh
python <builder-skill-dir>/scripts/run.py --factory <root> select
```

Read its JSON: `mode` (`one_shot` or `continuous`), `kill_switch`, `capacity` (concurrency, in-progress, available, remaining rate window) and `candidates`. Empty candidates with blockers listed is a valid, finished pass: report the blockers and stop.

The kill switch is a `STOP` file in the run directory (default `<project>/.factory-runs/`) or `FACTORY_STOP=1` in the environment. Never delete the STOP file; only the operator does.

## 2. Dispatch Build and Verify in parallel

```sh
python <builder-skill-dir>/scripts/run.py --factory <root> plan
```

The plan lists up to `budget.max_workers` workers, one task each, with a worker prompt rendered from worker-handoff.md. For each worker, start one subagent with that prompt, in an isolated worktree when the harness offers one, and have it perform `/factory-build` then `/factory-verify` for its single task only. Workers never share files: tasks with overlapping `allowed_paths` are not planned together. Do not add workers beyond the plan, and do not reuse a worker for a second task in the same pass.

Wait for every worker. Each returns status, revision, checks actually run, evidence and blockers. A worker that reports blocked, failed or budget exhaustion is recorded as such; do not retry it inside this pass without a new hypothesis, and never beyond `budget.max_repair_attempts`.

## 3. Release and Learn sequentially

When every worker has returned, perform `/factory-release` once for the pass. Pre-merge readiness requires each still-required check to pass for the exact revision; a READY handoff is still not merge or deploy authority. Then perform `/factory-learn` once, recording the pass outcome.

## 4. Record the pass

```sh
python <builder-skill-dir>/scripts/run.py --factory <root> record --run-id <id> --dispatched T1,T2 --outcome completed --notes "..." --apply
```

Run records live outside the factory directory so they never break integrity. They are what the rate limit, the dashboard and the next pass read.

## Continuous operation

A single session may loop passes only when `operations.issue_intake.mode` is `continuous`, `operations.autonomy.mode` is `bounded`, and the pass is within `budget.max_minutes`. Between passes, re-run `select`; stop when it reports the kill switch, no capacity or no candidates. For 24/7 coverage use an external scheduler instead of an in-session loop:

```sh
python <builder-skill-dir>/scripts/run.py --factory <root> schedule --kind cron
```

`schedule` renders a cron, launchd, Windows Task Scheduler or GitHub Actions definition from the recorded cadence and prints it. It installs nothing. Review the rendered definition and, within separately authorized scheduler scope, write it with `--write <path-outside-factory> --apply` and enable it yourself. See scheduling/README.md for each scheduler. Issue pickup from a GitHub repository uses a read-only issue snapshot (`select --issues <snapshot.json>`) exported by the authorized scheduler job; this skill never lists, labels or claims issues itself.

## Exit
Run ID, mode, workers dispatched, per-task status/revision/evidence, release handoff state and learn entry. The boundaries.md stop rules apply to the pass as a whole and to each worker.

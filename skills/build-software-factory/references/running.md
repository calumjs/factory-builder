# Running the factory

The seventh generated skill, `factory-run`, is the engine. The six phase skills
are procedures; `factory-run` selects work, drives them, and records each pass.
It adds no authority: every action it dispatches is bounded by policy.md, the
recorded budget and the autonomy controls.

## One pass

```sh
python scripts/run.py --factory /approved/project/.software-factory select
python scripts/run.py --factory /approved/project/.software-factory plan
```

`select` is read-only. It checks integrity, the kill switch, `budget.max_workers`
minus tasks already `in_progress`, the rate window (bounded autonomy only) and
task dependencies, then lists candidates and why the rest are blocked. Tasks whose
`allowed_paths` overlap another planned or active task are never selected
together; a task with no recorded paths is treated as overlapping everything.

`plan` adds one rendered worker prompt per candidate, built from
worker-handoff.md. The orchestrating session starts one worker per entry with its
own subagent mechanism (isolated checkout when the harness offers one), each
performing `factory-build` then `factory-verify` for its single task, waits for all
of them, then performs `factory-release` and `factory-learn` once. Nothing in the
helper starts a worker.

```sh
python scripts/run.py --factory ... record --run-id <id> --dispatched T1,T2 --outcome completed --apply
```

Run records are JSON files in `<project>/.factory-runs/` (override with
`--runs`, always outside the factory). They feed the rate limit and are the
operator's audit trail. The helper refuses a path inside the factory so
integrity is never disturbed.

## Issue pickup

A continuous factory does not read GitHub itself. The authorized scheduler job
exports a read-only snapshot and passes it with `select --issues snapshot.json`.
The helper applies the submitter allowlist, duplicate and dependency checks from
[operation.md](operation.md) and reports eligible issue IDs. An eligible issue
still goes through `factory-intake` to become a task; the helper never labels,
claims or comments.

## Schedules

```sh
python scripts/run.py --factory ... schedule --kind cron|launchd|windows|github [--every 120] [--builder /abs/skill/dir]
```

Rendering requires `issue_intake.mode: continuous` and `autonomy.mode: bounded`;
otherwise the factory runs only on a human kickoff. The interval comes from the
recorded cadence (minutes) or `--every`, with a 60-minute floor. The output is
printed, or saved with `--write <path-outside-factory> --apply`, and is never
installed: `crontab`, `launchctl`, `schtasks` or committing a workflow is the
operator's separate action. The generated `scheduling/README.md` and inactive
`scheduling/factory-run.example.yml` describe each route.

## Kill switch and stop rules

`<runs>/STOP` or `FACTORY_STOP=1` halts selection and every subsequent
dispatch. The helper never removes the file. A pass also stops on failed
integrity, exhausted `max_minutes`/`max_cost`, a failed required gate after
`max_repair_attempts`, missing authority or a data-boundary conflict, and
reports the smallest next human decision.

## Existing factories

`factory-run` and `scheduling/` are new contract files, so an older factory
adopts them through the [narrow reviewed update](existing-factory-update.md),
not by copying files into a hashed directory.

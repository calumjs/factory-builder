# Running the factory

The seventh generated skill, `/factory-run`, is the engine. The six phase skills
are procedures; `factory-run` selects work, drives them, and records each pass.
It adds no authority. The helper does not dispatch work or enforce policy,
budget or autonomy controls; independently authorized orchestration must do so.

## One pass

```sh
python scripts/run.py --factory /approved/project/.software-factory select
python scripts/run.py --factory /approved/project/.software-factory plan
```

`select` is read-only. It checks integrity, the kill switch, `budget.max_workers`
minus tasks already `in_progress`, the rate window (bounded autonomy only) and
task dependencies, then lists candidates and why the rest are blocked. Path
comparison is conservative and lexical; aliases and shared resources need separate
review. A task without recorded paths is blocked. Selection does not reserve work or
enforce rate, concurrency, budget or external authority. Establish a verified
exclusive dispatcher or atomic admission mechanism before authorized dispatch.

`plan` adds one rendered worker prompt per candidate, built from
worker-handoff.md. After separate authority and verified exclusive admission,
the orchestrator can dispatch scoped work. Integrate and reverify the exact
combined revision before any release handoff. Nothing here starts a worker.

```sh
python scripts/run.py --factory ... record --run-id <id> --dispatched T1,T2 --outcome completed --apply
```

Run records are JSON files in `<project>/.factory-runs/` (override with
`--runs`, always outside the factory). They are retrospective supplied claims for advisory rate calculations, not
reservations, independently verified events or budget enforcement. The helper refuses a path inside the factory so
integrity is never disturbed.

## Issue pickup

A continuous factory does not read GitHub itself. The authorized scheduler job
exports a read-only snapshot and passes it with `select --issues snapshot.json`.
Pass `--issue-policy policy.json` with a non-secret object such as
`{"repository":"owner/repo","ready_label":"ready","excluded_labels":["paused"]}`.
The helper requires an explicit matching repository and project-specific ready and
excluded label policy, then applies label, submitter, duplicate and dependency
checks. The snapshot and its claimed repository are untrusted and must be verified
within the authorized intake process; reported IDs are candidate data. An eligible issue
still goes through `factory-intake` to become a task; the helper never labels,
claims or comments.

## Schedules

```sh
python scripts/run.py --factory ... schedule --kind cron|launchd|windows|github [--every 120] [--builder /abs/skill/dir]
```

A proposal requires enabled continuous intake and bounded autonomy. The interval
comes from the recorded cadence or `--every`, with a 60-minute floor; unsupported
cron intervals and restricted windows are refused. Output is non-executable JSON,
never a runnable definition. Before any separately authorized scheduling action,
design and verify exclusive admission, actual rate/budget enforcement, stop
handling, scoped data and a platform-specific command. No scheduler is installed.

## Kill switch and stop rules

`<runs>/STOP` or `FACTORY_STOP=1` blocks new selections when checked. The helper
cannot stop a running worker or guarantee a later dispatch observes a changed signal. The helper never removes the file. A pass also stops on failed
integrity, exhausted `max_minutes`/`max_cost`, a failed required gate after
`max_repair_attempts`, missing authority or a data-boundary conflict, and
reports the smallest next human decision.

## Existing factories

`factory-run` and `scheduling/` are new contract files. The existing operations
updater does not add them. An older factory needs a separately reviewed selective
contract migration and backup; do not copy files into a hashed directory or
silently rebaseline it.

Optional `--recipe <nonsecret-json>` supplies an explicitly selected argv recipe:
`{"purpose":"factory-run","argv":["agent","--example"],"restrictions":"project-specific bounds"}`.
The format-specific fragment is inert review data, not a scheduler or authority;
no free-text recipe is selected automatically. Cron and GitHub previews use POSIX
shell quoting; Windows previews are for direct process arguments, not a shell.
Cron backslash-percent and GitHub expression markers are refused; review platform
semantics and execution scope before any separately authorized integration.

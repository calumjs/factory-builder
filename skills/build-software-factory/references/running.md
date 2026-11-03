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
review. Allowed paths are project-relative **literal paths**, not glob expressions;
brackets in a name such as `app/contacts/[id]/` are literal. Quote paths when a shell
could expand them. Wildcards `*` and `?`, traversal, redirected paths and ambiguous
aliases remain blocked. A task without recorded paths is blocked. Selection does not reserve work or
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
`--runs`, always outside the factory). Place this top-level option before the
subcommand, for example `run.py --factory <factory> --runs <outside-path> select`.
They are retrospective supplied claims for advisory rate calculations, not
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

The snapshot is a JSON array, not raw `gh issue list` output. Each item requires
nonempty string `id` and `submitter`, and string-array `labels`. Optional `title`
and `created_at` must be strings (default empty); optional `depends_on` must be a
string-ID array (default empty). `created_at` sorts lexically; use provider ISO
timestamps consistently. For example, [example-issue-snapshot.json](../assets/example-issue-snapshot.json):

```json
[{"id":"42","title":"Example","submitter":"operator","created_at":"2026-01-01T00:00:00Z","labels":["ready"],"depends_on":[]}]
```

An authorized exporter must explicitly map its provider's number, author and label
objects to this schema and verify repository identity and dependency history. Raw
GitHub objects and missing labels are not accepted as verified candidates. Confirm
the configured `issue_intake.github_scope` exactly matches the policy repository;
a reported ID alone does not establish provenance or authorization.

Example export design, only for an already authorized repository read:

```sh
gh issue list --repo OWNER/REPO --state open --limit 1000 --json number,title,author,labels,createdAt | jq 'map({id:(.number|tostring),title,submitter:.author.login,labels:[.labels[].name],created_at:.createdAt,depends_on:[]})' > snapshot.json
```

This capped export may omit issues; verify completeness and repository identity.
GitHub dependency state is **not** supplied by this command. Treat its empty
`depends_on` values as unverified placeholders: reconcile actual dependency and
processed-issue history before using the snapshot. Keep the verified repository
in the separate policy object and match `issue_intake.github_scope`; repository
identity is not inferred from a per-item field. Exporting is not intake approval.

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
silently rebaseline it. Inventory the exact installed version and target, prepare
the missing files and selective manifest entries in private scratch, review them
against the independently accepted baseline, then use the manual procedure in
[recovery.md](recovery.md). Retain living records and project customizations; recheck
integrity and discovery after authorized adoption. This procedure does not activate
dispatch or schedules; no automatic Run migration is currently provided.

For a six-phase factory, first check whether
`.claude/skills/factory-run/SKILL.md` and the named `scheduling/` files are present
in both the tree and manifest. A passing `scaffold.py --check` attests the recorded
file set; it does not assert that optional new Run files have been adopted. Use
the trusted installed builder's `run.py --factory <existing-factory> --runs
<outside-path> select` for a read-only advisory pass before adoption.

For manual adoption, render a disposable candidate from the reviewed project
config/research using the trusted builder. Inspect only the missing
`.claude/skills/factory-run/SKILL.md` and `scheduling/` contract files, their phase
references and assumptions against the existing factory. Prepare an exact file
list and selective manifest entries, retaining all existing contracts, living
records and customizations. Complete recovery section 1's backup, full-diff review,
stable-writer and manifest-last steps; then check integrity and discover the
new skill from the project's intended agent surface. Do not replace the factory
with the rendered candidate. Missing authority or incompatible phase contracts
blocks adoption. No `--run-runtime` updater switch is implemented.

Optional `--recipe <nonsecret-json>` supplies an explicitly selected argv recipe:
`{"purpose":"factory-run","argv":["agent","--example"],"restrictions":"project-specific bounds"}`.
The format-specific fragment is inert review data, not a scheduler or authority;
no free-text recipe is selected automatically. Cron and GitHub previews use POSIX
shell quoting; Windows previews are for direct process arguments, not a shell.
Cron backslash-percent and GitHub expression markers are refused; review platform
semantics and execution scope before any separately authorized integration.

# Scheduling the factory — inactive templates

Nothing in this folder is installed or enabled by scaffolding. It documents how
to run `/factory-run` on a schedule once the operator has confirmed
`operations.autonomy.mode: bounded` (named submitters, positive rate limit, kill
switch) and holds authority over the chosen scheduler. One-shot mode needs none
of this: start Claude Code in the project and invoke `/factory-run`.

## Render a definition

```sh
python <builder-skill-dir>/scripts/run.py --factory <root> schedule --kind cron
python <builder-skill-dir>/scripts/run.py --factory <root> schedule --kind launchd
python <builder-skill-dir>/scripts/run.py --factory <root> schedule --kind windows
python <builder-skill-dir>/scripts/run.py --factory <root> schedule --kind github
```

The helper reads the recorded cadence (`operations.issue_intake.cadence`, in
minutes when numeric; otherwise `--every <minutes>`), applies the hourly floor,
and prints a definition. Add `--write <path> --apply` to save it somewhere
outside `.software-factory/` for review. Enabling it (crontab -e, launchctl
load, schtasks /create, committing a workflow) is a separate, authorized action.

## What a scheduled pass does

Each firing runs one factory-run pass with the headless recipe recorded in
`tools.json` (`run.py schedule` refuses to render without a confirmed one; the
scheduler is not a harness, so it needs the literal command). The pass selects work,
dispatches up to `budget.max_workers` workers, releases and learns, then records
the run in `.factory-runs/`. The rate limit is enforced from those records, so a
scheduler that fires more often than `max_items_per_hour` simply produces empty
passes.

## Kill switch

Create `.factory-runs/STOP` (any content) or export `FACTORY_STOP=1` for the
scheduler's environment. Every pass checks it before selecting work and before
each dispatch. Remove the file only by operator decision.

## Issue pickup

A continuous factory reads a snapshot file, not GitHub directly. The scheduler
job exports eligible issues (read-only, authenticated with its own scope) to a
JSON list and passes it with `select --issues snapshot.json`. Each entry has
`id`, `title`, `submitter`, `created_at` and optional `labels` and
`depends_on`. Submitters outside `autonomy.allowed_submitters` are rejected and
reported. The helper never labels, claims, comments on or closes issues.

`factory-run.example.yml` shows the GitHub Actions shape: scheduled and manual
triggers, minimal permissions, the snapshot export, the headless pass and the
run record uploaded as a workflow artifact. Adapt it in trusted CI configuration
with a pinned builder checkout; do not run a PR-supplied copy.

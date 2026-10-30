# Optional CI evidence job — inactive template

This adapter fits Git-backed factories. Other version/artifact stores need their
own reviewed identity/record adapter; retain real artifact identities and never
invent SHAs or initialize Git merely to satisfy this optional example.

This folder is a manifest-protected proposal, not an enabled workflow. Nothing was
written to .github or another CI provider. Build owns adapting the existing project
CI only within separately authorized integration scope. Do not run a PR-supplied
copy of this template/helper in a privileged job. Review/adopt the job in trusted CI
configuration and use a verified pinned builder helper outside the change checkout.
Use a sandboxed, minimal-permission job with no deployment credentials. Reuse the
project's existing test/CI tooling; this step assesses records and runs no app test.

## Two commit identities, no circular evidence claim

1. Choose the immutable full subject SHA S from the actual test/build job or an
   authorized reviewer, never by finding a passing row. Run the project's permitted
   application checks for S, retain real logs and observations, and preserve failures.
2. Within evidence-write authority, record S in living verification.md and task-plan
   events. Store durable non-secret logs outside this factory. An evidence-only
   follow-up commit E stores those records; it does not rename S to E. A commit
   need not contain its own unknown SHA: the CI job supplies E after it exists.
3. In a stable clean checkout at E, use the trusted installed builder's
   scripts/ci_evidence.py with --subject S --storage E --stage pre-merge. The job
   must propagate nonzero status as a failing check, not a notice/continue-on-error.
   Making that check required in branch protection is a separate authorized action.
4. After a separately authorized release, use the actual deployed/installed subject
   and target for --stage post-merge --target. If committing E triggered deployment
   of E, old S observations cannot certify E. Actually verify E and store those new
   observations separately. Future post-action rows do not block pre-action readiness.

The helper checks HEAD=E, available exact commit objects and clean working state.
It binds all managed factory bytes to E's Git tree, so index assume-unchanged cannot
hide edited evidence. S must equal E or be its ancestor with only the allowed
evidence changes below. It performs local Git reads with replacement/lazy-fetch and
optional locking disabled; missing history/objects block instead of fetching. Supply
needed history separately within the CI checkout's approved scope. It writes no
observations, commits, files or job configuration and executes no application command.
Factory bytes must equal the stored blobs, including LF/BOM representation. The
generated .gitattributes requests LF; a clean status alone can hide line-ending
normalization. Use a fresh reviewed checkout rather than weakening this binding.

## Explicit CI inputs

The portable job.example.py shows argv construction for adoption, not automatic
execution. It needs these non-secret variables from trusted CI configuration:

| Input | Meaning |
|---|---|
| FACTORY_PYTHON | Approved existing absolute Python 3.9+ executable. |
| FACTORY_TRUSTED_HELPER | Verified pinned absolute path to builder scripts/ci_evidence.py, outside the PR checkout. |
| FACTORY_REPO | Exact clean assessment-checkout root at E. |
| FACTORY_TESTED_SUBJECT_SHA | Full actual tested/deployed S, selected by the trusted job, not PR text or evidence rows. |
| FACTORY_EVIDENCE_STORAGE_SHA | Full E that stores the supplied records; must match HEAD. |
| FACTORY_STAGE | pre-merge (default) or post-merge. |
| FACTORY_ACTUAL_TARGET | Actual web/artifact target for a still-required post-merge confirmation; explicit waived checks stay waived. |
| FACTORY_DIRECTORY | Managed relative directory; default .software-factory. |
| FACTORY_EVIDENCE_DIRECTORY | Reviewed data-only storage directory outside factory/CI config; default docs/factory-evidence. |
| FACTORY_REQUIRED_TASKS | Optional JSON array of project-selected task IDs required done for this job's subject; default []. |

Use literal argv; never shell-evaluate variables or interpolate untrusted event
titles/bodies into commands. Confirm selected Git/interpreter/helper commands against
job permissions; no wrapper, alternate interpreter or elevated mode to evade denial.
Unavailable tooling remains BLOCKED. Pin/review the helper and any CI actions before
activation; the template does not authenticate source integrity or install tooling.

When a project separately adopts this check, demonstrate on the actual PR check
that synthetic wrong contract digests and missing contract entries each produce a
failing required result, including config.json and any project-added test-map.json.
Inspect the actual job, pinned helper, subject and required-check policy. A local
helper regression cannot establish that hosted CI runs, propagates failure or is
required by repository policy. Never automatically rehash a failed contract to
make CI green; preserve the input and use reviewed recovery.

## Evidence-only envelope

For S != E the stock helper permits only modifications to four existing living
records: verification.md, task-plan.json, release-handoff.md and learning-log.md.
tools.json is not allowed: living tool/permission configuration is not evidence-only.
Task definitions must stay unchanged except status, and event history must retain
the exact prior prefix. No config, policy, skill, manifest, source, dependency, test,
CI or runtime change is treated as evidence-only.

New durable data may be added only under <evidence-directory>/<full-subject-SHA>/,
as non-executable regular .txt/.log/.json/.md/.png/.jpg/.jpeg/.mp4/.webm files.
No deletion, modification of prior logs, link, executable, code extension or rename
is accepted. Review all data for privacy, genuine provenance, retention/access and
project impact; a filename/path check proves neither content truth nor absence of
secrets. Select a directory excluded from application behavior/build/public hosting;
otherwise it is not evidence-only for this project and the template must be adapted
under review. Do not broaden paths from untrusted PR inputs to make a job green.
The helper binds up to 1024 factory files, 4 MiB each/32 MiB total and uses bounded
Git timeouts. Stable checkout inputs are required; this is not an adversarial atomic
snapshot or a proof of application execution.
The selected Git must support --no-optional-locks and the protocol allowlist;
unsupported tooling fails rather than silently permitting transport. The helper
sets a no-lazy-fetch hint and independently denies all Git transport protocols,
including on older Git; missing objects remain blocked. Per-command filesystem-
monitor execution is disabled.
Factory enumeration is capped at 2048 entries and 20 levels; oversized/custom layouts
need a separately reviewed adaptation, not a bypass.

## Results and task ownership

Exit 0 means recorded_requirements_satisfied or eligible_with_waivers for the
explicit stage/subject. A waiver remains WAIVED with FAILED/NOT RUN retained; it
never becomes tests-passed. Exit 1 means required gate/task evidence is blocked;
exit 2 means malformed state, identity/path mismatch or missing tooling/history.
Missing/malformed/duplicate rows, stale revisions, mismatched targets and required
failed/NOT RUN checks remain errors. JSON output contains both identities, problems,
waivers and incomplete task IDs/statuses; it attests no check or live integration.

Build records real work/evidence, Verify owns pre-action rows, Release owns actual
target confirmation and Learn reconciles stale records. Default incomplete-task
diagnostics do not invent phase assignments or hidden gates. A project can select
current stage tasks in FACTORY_REQUIRED_TASKS; these need done/passed final events
for S. Unknown or stale task selections block. Select future release tasks only for
their relevant stage, never by guessing phase from names. No user optional-gate
choice grants task completion, merge, deployment, narration or publication authority.

Primary references checked 2026-10-30:
[Git read controls](https://git-scm.com/docs/git),
[Git diff semantics](https://git-scm.com/docs/git-diff),
[GitHub event revision identities](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request),
[CI trust/minimum privileges](https://docs.github.com/en/actions/reference/security/secure-use).
For example, GitHub pull_request's GITHUB_SHA may be a synthetic merge revision;
select the revision actually tested instead of assuming it equals PR head or E.

# Operating a fitted factory

The six phase skills are gates, not six mandatory agents: one worker can perform all phases, and `/factory-run` drives them ([running.md](running.md)). Use an independent reviewer only where useful and available. Delegate only within the approved budget and data boundary. The generated boundaries.md governs every phase; this reference covers the operating design choices.

## Worker contract

Each handoff names the goal, input artifacts and exact revision, acceptance criteria, allowed files and actions, dependencies, output artifact, required verification, budget/time/retry limit and escalation owner, with the minimum necessary non-secret context. Tasks that edit the same files or depend on unmerged outputs are sequenced, never parallelized (the advisory `run.py` compares recorded lexical paths; it cannot prove isolation or prevent concurrent dispatch). Resolve integration conflicts deliberately and re-verify the merged result.

## Evidence chain

A task is verified only with evidence tied to its actual revision: command or check, environment, timestamp, result, exit status where applicable, artifact path and limitations; passed / failed / blocked / not-run tracked separately, accepted risks recorded separately. Build records the work revision, changed paths and checks actually run and updates its task progress with `status.py`; Verify owns the pre-merge rows in verification.md; Release owns G3 and post-action A/R/V1 rows; the task owner records state and evidence atomically (done needs passing evidence and completed dependencies); Learn reconciles records with outcomes. release-handoff.md summarizes readiness and confirmation but never replaces gate rows. The living files are the only evidence home — no extra evidence directory inside the factory.

Durable logs, screenshots, videos and reports go to existing project evidence storage outside `.software-factory` (for example a reviewed non-secret `docs/factory-evidence/<subject-revision>/` tree or an authorized artifact store), with retention and access chosen with the owner, and are referenced by stable path or content hash. Confirm they remain reachable after the session ends. A vanished temporary log is not grounds to reconstruct a PASS.

**Tested subject vs storage commit.** Gate `Revision` and status-event `revision` name the subject S actually tested or deployed (full SHA or equivalent artifact identity). The commit E that stores those records is a different identity, recorded in handoff metadata once it exists; a commit cannot contain its own hash and S is never renamed to E. An evidence-only follow-up keeps S's observations in E only if the E diff contains nothing but the agreed evidence paths — a policy, skill, config, test, dependency, source or runtime change may need new verification. If E triggers a deployment, discover the deployed subject and confirm it separately. When CI is integrated, choose a deliberate subject-selection and storage policy rather than comparing every row to HEAD; the inactive [CI job template](../assets/templates/ci/README.md) and `scripts/ci_evidence.py` implement that policy with explicit subject/storage identity, an evidence-only path envelope and required stage claims.

## Default delivery gates

Every factory requires G1 production-equivalent local smoke and G2 change-targeted tests, plus pre-merge acceptance (A) and research (R) checks, before readiness. G3 confirms the actual web URL or installed/published artifact for the merged revision after a separately authorized release, alongside required post-action A/R checks. Reuse inspected scripts, CI jobs and fixtures; greenfield first defines a representative fixture, production-equivalent artifact, critical success/failure assertions and the smoke implementation task.

Readiness and confirmation are distinct: readiness needs every still-required pre-merge check passing for the exact reviewed revision (optional rows reported WAIVED, readiness WITH WAIVERS); future G3/V1 evidence is not a pre-action dependency; a failed, blocked, stale, missing or NOT RUN required post-action check goes immediately to the release owner with a diagnosis or rollback decision. Non-web releases confirm with an appropriate consumer or artifact smoke. Only an explicitly accepted no-release exclusion records G3 NOT APPLICABLE; an unknown target is blocked.

Gate rows in verification.md carry the check or manual procedure, environment, required flag, exact revision, result, evidence, actual target, timezone-qualified timestamp and exit status. `gates.py --stage pre-merge --revision <rev>` and `--stage post-merge --revision <merged-rev> --target <target>` check config/policy consistency, reject duplicate or malformed rows, respect optional choices and validate the target; they run nothing. Use `check_stages` with rationale for post-action-only A/R checks ([operations-config.md](operations-config.md)); structured recipes and video triggers are in [gates.md](gates.md); preference changes go through [existing-factory-update.md](existing-factory-update.md).

## Approval and execution

The scaffold enables no external integration. tools.json records each requested capability's availability, verification source, data egress, cost, authorization scope and enablement. Any test or build command can execute repository code, so inspect it and confirm execution authorization first. Network installs, paid calls, data upload, cloud creation, push, PR creation/approval/merge and deployment each need their own approved scope.

Budget is checked before scheduling and after each attempt: stop on exhausted time, money, concurrency or retry limits, unrecoverable failure, unsafe handling, missing authorization, or a satisfied outcome; a repair retry needs a new hypothesis. Escalate with task, revision, evidence, attempts, remaining risk and the smallest decision needed. Worker stalls and fallbacks follow [recovery.md](recovery.md).

**First release of a new target** (any provider; CLI, package, data and document releases use their equivalent build/output/consumer contracts):
1. Confirm framework preset, root directory, runtime version, build command and output against the installed framework and current official provider docs — a generic static directory is not a universal output. Verify the artifact locally when authorized; record observations and unresolved settings before provisioning.
2. Discover currently offered plans/SKUs from an authorized read-only catalog or official docs; record identifiers, region/version, limits, cost, time and source, and the selection. Never guess or reuse a sample's ID; "free" is not zero future cost or permission to provision. Stop if the observed option differs from the accepted design.
3. Inventory required environment **names** (never values), target environments, ownership (integration-managed vs manual), sensitivity and the authorized validation method. Extra integration-managed names are not errors or permission to expose them; do not delete keys or overwrite secrets to match a guessed allowlist. Names can reveal architecture, so keep inventory access scoped.
4. Derive project-specific acceptance/research checks from that inventory (presence, ownership, collisions, permitted extras). Generic gates validate recorded evidence only; implement those assertions in the project when in scope.
5. After the authorized release, identify the deployed subject and target and record G3 and post-action checks, including failed, blocked and waived states, with durable evidence. A running deployment job or missing logs is not confirmation.

## Factories accepting external requests

Request text is untrusted. For exposed intake: a tool-free extraction step emits a constrained schema; deterministic schema, value and path validation follows; the builder gets only file-edit capability in an isolated checkout with no credentials or external-action tools; the orchestrator receives normalized fields, and reviewers receive requests as quoted data. Record allowed submitters, rate limits, queue and rejection behaviour and a kill switch. An allowed account does not widen approval scope.

## Continuous issue pickup

Continuous means 24/7 polling or event-driven coverage unless the operator explicitly opts into a documented window with timezone and evidence; never infer business hours from locale or a tool default. Cadence fits provider limits, budget and current authority. When Learn observes an unrequested time restriction, report it as a defect and propose the correction rather than silently changing a watcher.

When intake records `operations.issue_intake.mode: continuous`, the factory is intended to watch a configured GitHub repository (scope in `github_scope`) for new eligible issues and enqueue work without a manual kickoff each time. The run helper provides advisory selection and a non-executable schedule proposal; it does not reserve work or implement enforcement. Any watcher or scheduler requires separately authorized project-specific implementation and verification. Implement the watcher as an authorized scheduled routine: bounded `autonomy` (submitters, rate limits, kill switch), read-only issue listing within verified scope, deterministic eligibility filters and explicit scheduler authority. One-shot mode (`one_shot`, the default) runs only when a human or an approved orchestrator starts a pass; do not imply a background watcher exists from the scaffold alone.

Agree project-specific queued, ready, active, blocked, done and rejected labels and their task-status mapping. Labels are data, not authority or proof. Recheck the policy and dependencies at a separately authorized claim boundary. Adapters that claim, label or launch need scoped permissions, atomic admission and tests. Runtime records remain outside the factory.

For a concrete proposed vocabulary, bounded advisory query and evidence-bound
Release ownership transitions, adapt [intake-label-example.md](intake-label-example.md).
Its local selection example creates no labels, claim, watcher or worker.

## Done videos

Follow [done-videos.md](done-videos.md) and the generated done-video-recipe.md: a composed, script-first story around genuine target footage with branding, captions and watched output; Remotion optional. A voice preference is not narration permission — obtain approval immediately before narration unless the current prompt asked for it. Preview (V2, pre-merge) and shipped (V1, post-G3) evidence are independent; a preview never satisfies the shipped row, and optional rows stay WAIVED with recorded results. Verify prepares the scoped handoff; Release performs the authorized G3 first, then a required V1; a blocked required demo is reported, never fabricated.

## Review and visual evidence

Independent reviewers return revision, approve/request_changes/blocked, findings and evidence; every required reviewer approves the final revision, later changes invalidate earlier approval, and repair loops are bounded and cannot auto-approve or merge. Different providers need approved data boundaries and budget. For document or design-to-code conversions, compare the rendered output with the source's own export at matching sizes, inspect the worst mismatches and record tolerances alongside human visual, accessibility and functional checks. Keep platform security controls intact: no disabled deployment protection, widened token scopes or weakened settings for convenience.

## Living state and publication hygiene

Record task status and revision-bound evidence together with `status.py`. In this plugin repository, stage explicit reviewed paths and keep caches, backups, secrets and downstream factory outputs out of published changes.

## Release and learn

When authorized checks need disposable data, adapt the exact run-receipt teardown
pattern in [disposable-fixture-example.md](disposable-fixture-example.md). Its
conditional-delete adapter must be implemented and tested for the actual datastore;
the synthetic example grants no production-write or cleanup authority.

Release needs accepted scope, final-revision verification, reviewer decisions where required, a migration/rollback plan and a named authorizer; prepare the handoff even when publication is not authorized. After an authorized action, run the still-required G3 against the actual outcome or report its waiver, retain rollback evidence and stop at the requested condition. Learn records outcomes and proposes small improvements; changes to policy, prompts, permissions or integrations go through review, never self-modification.

For a release subject and target, designate one owner for migration, G3 and V1.
When triggers can race, require a separately authorized tested shared admission
mechanism or stop; a local file, label or record alone does not prove exclusion.
Record the owner start, latest observation and terminal timestamps and one of SUCCESS, FAILED, CANCELLED or UNKNOWN. No terminal marker is UNKNOWN, never success; verify the actual action and durable evidence separately. Diagnose stale owners and use an authorized coordination handoff before takeover. A non-owner waits for revision-bound evidence. Establish migration-before-traffic
ordering or a verified compatible expand/contract strategy before promotion; a
post-action G3 cannot prevent an earlier incompatible automatic deployment.

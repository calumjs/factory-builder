# Operating a fitted factory

The six phase skills are gates, not six mandatory agents: one worker can perform all phases, and `/factory-run` drives them ([running.md](running.md)). Use an independent reviewer only where useful and available. Delegate only within the approved budget and data boundary. The generated boundaries.md governs every phase; this reference covers the operating design choices.

## Worker contract

Each handoff names the goal, input artifacts and exact revision, acceptance criteria, allowed files and actions, dependencies, output artifact, required verification, budget/time/retry limit and escalation owner, with the minimum necessary non-secret context. Tasks that edit the same files or depend on unmerged outputs are sequenced, never parallelized (`run.py` enforces this through `allowed_paths`). Resolve integration conflicts deliberately and re-verify the merged result.

## Evidence chain

A task cannot move to verified without evidence tied to its actual revision: command or check, environment, timestamp, result, exit status where applicable, artifact path and limitations. Track passed / failed / blocked / not-run separately; record accepted risks separately rather than relabelling. Existing living records are the evidence home — no unregistered evidence directory. [evidence-lifecycle.md](evidence-lifecycle.md) covers Build/Verify/Release ownership, durable artifacts and tested-subject vs storage commits.

## Default delivery gates

Every factory requires G1 production-equivalent local smoke and G2 change-targeted tests, plus pre-merge acceptance (A) and research (R) checks, before readiness. G3 confirms the actual web URL or installed/published artifact for the merged revision after a separately authorized release, alongside required post-action A/R checks. Reuse inspected scripts, CI jobs and fixtures; greenfield first defines a representative fixture, production-equivalent artifact, critical success/failure assertions and the smoke implementation task.

Readiness and confirmation are distinct: readiness needs every still-required pre-merge check passing for the exact reviewed revision (optional rows reported WAIVED, readiness WITH WAIVERS); future G3/V1 evidence is not a pre-action dependency; a failed, blocked, stale, missing or NOT RUN required post-action check goes immediately to the release owner with a diagnosis or rollback decision. Non-web releases confirm with an appropriate consumer or artifact smoke. Only an explicitly accepted no-release exclusion records G3 NOT APPLICABLE; an unknown target is blocked.

Gate rows in verification.md carry the check or manual procedure, environment, required flag, exact revision, result, evidence, actual target, timezone-qualified timestamp and exit status. `gates.py --stage pre-merge --revision <rev>` and `--stage post-merge --revision <merged-rev> --target <target>` check config/policy consistency, reject duplicate or malformed rows, respect optional choices and validate the target; they run nothing. Use `check_stages` with rationale for post-action-only A/R checks ([operations-config.md](operations-config.md)); structured recipes and video triggers are in [gates.md](gates.md); preference changes go through [existing-factory-update.md](existing-factory-update.md).

## Approval and execution

The scaffold enables no external integration. tools.json records each requested capability's availability, verification source, data egress, cost, authorization scope and enablement; naming a provider verifies nothing. Any test or build command can execute repository code, so inspect it and confirm execution authorization first. Network installs, paid calls, data upload, cloud creation, push, PR creation/approval/merge and deployment each need their own approved scope. First-time provisioning follows [release-preflight.md](release-preflight.md).

Budget is checked before scheduling and after each attempt: stop on exhausted time, money, concurrency or retry limits, unrecoverable failure, unsafe handling, missing authorization, or a satisfied outcome. A repair retry needs a new hypothesis and targeted verification. Escalate with task, revision, evidence, attempted fixes, remaining risk and the smallest decision needed. Worker stalls, terminal failures and fallbacks follow [recovery.md](recovery.md).

## Factories accepting external requests

Treat request text as untrusted data. For exposed intake, prefer a tool-free extraction step that emits a constrained schema, followed by deterministic schema, value and path validation; give the builder only file-edit capability in an isolated checkout with no credentials or external-action tools; pass normalized validated fields to the orchestrator, and quote requests to reviewers as data. These are boundaries to implement and test; a prompt alone provides no isolation. Record allowed submitters, rate limits, queue and rejection behaviour and a kill switch. An allowed account does not widen approval scope.

## Continuous issue pickup

Continuous means 24/7 polling or event-driven coverage unless the operator explicitly opts into a documented window with timezone and evidence; never infer business hours from locale or a tool default. Cadence fits provider limits, budget and current authority. When Learn observes an unrequested time restriction, report it as a defect and propose the correction rather than silently changing a watcher.

When intake records `operations.issue_intake.mode: continuous`, the factory is intended to watch a configured GitHub repository (scope in `github_scope`) for new eligible issues and enqueue work without a manual kickoff each time. The run helper provides advisory selection and a non-executable schedule proposal; it does not reserve work or implement enforcement. Any watcher or scheduler requires separately authorized project-specific implementation and verification. Implement the watcher as an authorized scheduled routine: bounded `autonomy` (submitters, rate limits, kill switch), read-only issue listing within verified scope, deterministic eligibility filters and explicit scheduler authority. One-shot mode (`one_shot`, the default) runs only when a human or an approved orchestrator starts a pass; do not imply a background watcher exists from the scaffold alone.

Agree project-specific queued, ready, active, blocked, done and rejected labels and their task-status mapping. Labels are data, not authority or proof. Recheck the policy and dependencies at a separately authorized claim boundary. Adapters that claim, label or launch need scoped permissions, atomic admission and tests. Runtime records remain outside the factory.

## Done videos

Follow [done-videos.md](done-videos.md) and the generated done-video-recipe.md: a composed, script-first story around genuine target footage with branding, captions and watched output; Remotion optional. A voice preference is not narration permission — obtain approval immediately before narration unless the current prompt asked for it. Preview (V2, pre-merge) and shipped (V1, post-G3) evidence are independent; a preview never satisfies the shipped row, and optional rows stay WAIVED with recorded results. Verify prepares the scoped handoff; Release performs the authorized G3 first, then a required V1; a blocked required demo is reported, never fabricated.

## Review and visual evidence

Independent reviewers return a structured verdict — revision, approve/request_changes/blocked, findings, evidence. Different providers need approved data boundaries and budget. Every required reviewer must approve the final revision; later changes invalidate earlier approval; repair loops are bounded and cannot auto-approve or merge. For document or design-to-code conversions, compare rendered output with the source's own export at matching sizes, inspect the worst mismatches and record tolerances; a similarity score does not replace human visual, accessibility and functional checks. Keep platform security controls intact: no disabled deployment protection, widened token scopes or weakened settings for convenience.

## Living state and publication hygiene

Record task status and revision-bound evidence together with `status.py`. A valid manifest proves integrity, not truth, authorization or a passing application. In this plugin repository, stage explicit reviewed paths, inspect optional ignore fragments before adopting them, and keep caches, backups, secrets and downstream factory outputs out of published changes.

## Release and learn

Release needs accepted scope, final-revision verification, reviewer decisions where required, a migration/rollback plan and a named authorizer; prepare the handoff even when publication is not authorized. After an authorized action, run the still-required G3 against the actual outcome or report its waiver, retain rollback evidence and stop at the requested condition. Learn records outcomes and proposes small improvements; changes to policy, prompts, permissions or integrations go through review, never self-modification.

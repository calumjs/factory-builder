# Inactive post-deployment verification adapter

Use this recipe when a web project's G3 smoke should follow a deployment, including
when a Vercel integration does not deliver GitHub deployment events. This is an
adoption proposal, not an installed workflow, provider integration, test runner or
release authorization. The Python adapter only prints a plan; exit 0 means that
the supplied inputs matched, never that G3 ran or passed. No helper probes a URL,
polls a provider, installs dependencies, writes evidence or changes requiredness.

The assets are [the disabled workflow](post-deploy-smoke.yml.example),
[the plan adapter](post-deploy.example.py) and
[an illustrative context](post-deploy-context.example.json).
Keep the adapter beside the existing trusted `job.example.py`; it reuses that
template's literal `ci_evidence.py` argument builder. Read the
[CI evidence contract](README.md) before adoption. The assets
stay outside `.github/workflows`; copying the YAML still leaves its job disabled
and its first step refusing unconfigured use. A skipped job is not G3 evidence.
This slice supplies the adapter and adoption procedure, not a ready hosted check.
Fresh factories include this inactive bundle as manifest-protected proposals.
Existing factories are unchanged: use the complete pinned installed builder bundle
for planning, or separately review adding its files/contracts using the documented
recovery process. Copying only a new README is not adoption of missing dependencies.

## Trusted project bridge and exact identities

1. Separately review the workflow, runner, pinned helpers/interpreter, artifact
   upload action, permissions, project recipe and target. Use project existing
   commands and approved credentials only; do not give a privileged job untrusted
   pull-request code. Do not use `pull_request_target` to run candidate commands.
   The event's ref, body, title, URL and manual inputs cannot select executable
   code, checkout paths, interpreter, credentials, permissions or a shell command.
2. A trusted bridge independently verifies the intended merged full SHA **S** in
   the configured repository and the current READY provider deployment's immutable
   ID, exact SHA, environment and approved HTTPS target. Branch names, a successful
   build, event `success`, and a 200 response alone do not establish that identity.
   Use the merge's captured SHA, not whatever `main` or a mutable alias points to
   later. This document does not supply a provider-specific polling implementation.
3. Provision the exact source/test checkout at S. Both the approved interpreter
   and pinned evidence helper must be outside that checkout and the later evidence
   checkout **E**. The adapter checks path separation, not executable provenance,
   checkout contents, symlink stability or the truth/freshness of supplied claims.
   The trusted bridge must verify those boundaries and prevent mutation during use.
4. Copy the project's reviewed structured `smoke_gates.checks.G3` recipe shape into
   context: `command` argv, `environment`, `env_names`, and web `target` including
   its declared `base_url_env`. This web-only adapter requires HTTPS and exact target
   equality. It does not parse prose into commands or infer required gates. Missing
   recipes, artifact-only/no-release projects and deliberate exclusions need their
   own project-fitted path; do not invent a smoke command or force optional rows.
5. Build context from trusted policy and independent facts, never by copying event
   fields into the supposedly independent deployment object. Every illustrated
   value must be replaced. `verification_reference` identifies nonsecret supporting
   evidence; it is not authenticated or fetched. Only variable names, never secrets,
   belong in context. All paths and recipe data printed in the plan are intentional
   local output; do not publish the context/plan indiscriminately.

Invoke the pinned adapter with approved absolute Python and adapter paths:

```text
python -B /trusted/templates/ci/post-deploy.example.py --context /trusted/context.json --event /runner/event.json
```

Event mode accepts a native GitHub event with unrelated fields but extracts only
`repository.full_name`, `deployment.id/sha/environment` and
`deployment_status.state/environment/environment_url`. Both environment labels must
exactly match this supported recipe; an overridden/conflicting label is refused.
The positive GitHub deployment ID must match independently captured facts. Use
`environment_url` for the application URL: GitHub's `target_url`/`log_url` describe
deployment output. If environment_url is absent, do not use the log URL; investigate
or use the explicit manual path below. No prefix SHA or URL normalization is used.

Context schema 1 has exactly the fields shown in the example. Full IDs are lowercase
40/64 hex; S and E use the same format. Inputs are strict JSON (no duplicate keys or
nonfinite numbers), at most 1 MiB each. Argv has 1–64 nonempty single-line elements
of at most 2000 characters; environment names are unique, at most 64. Required task
IDs are unique, at most 256. URL credentials/query/fragment are refused. The adapter
returns `plan_only`, selected S/E/target, literal smoke argv/cwd/environment plan,
and the existing post-merge assessment argv. Canonical input hashes bind the plan
to these supplied inputs; they are not signed evidence or a replay-prevention lock.
Invalid input exits 2 with a fixed diagnostic and no partial plan. It executes
nothing, including commands containing shell metacharacters.

## Authorized execution and real evidence

The separately implemented bridge consumes this plan only after authorization.
Run approved argv with `shell=False`, in source S, with a bounded timeout and only
approved environment values. Set the declared base URL variable from the approved
target, not an event URL. A mutable production alias can move during a test: verify
the provider ID/S/target immediately before and after smoke, or mark the attempt
UNKNOWN/blocked. Prefer an authorized immutable deployment URL where appropriate;
checking it does not automatically prove the production alias is serving it.

Preserve real smoke exit status, timestamps, deployment identity checks and the
project's actual Playwright report/trace when applicable. Add a separately reviewed
upload step pinned to an immutable action revision, explicit report directory,
missing-file error and project-approved retention. Redact tokens, private URLs and
user data; never upload environment dumps or context containing sensitive paths.
Upload failure is an evidence gap, not a pass. Failure/cancellation must retain
the failed or incomplete attempt; `always()` cannot promise to run after termination.

Use the existing gate/batch record transaction (installed builder reference
`references/batch-observations.md`) to record
actual G3 observations for S and the actual target with preserved failure history.
The adapter neither writes PASSED nor creates a waiver. Commit authorized evidence
as E using the existing allowed envelope; then assess clean E with the printed
`ci_evidence.py --stage post-merge --subject S --storage E --target ...` argv. Keep
all required acceptance/review/video records and explicit task requirements visible;
CI exit 0 can include visible optional waivers and never proves application execution.
Propagate blocked/error exit codes. If committing E redeploys E, evidence for S
does not certify that new deployment. Reverify the applicable exact subject.

## Trigger liveness and manual fallback

During the first separately authorized deployment after adoption, capture a bounded
deadline and verify all three links: a GitHub Deployment for exact S/environment,
a corresponding success status, and the expected workflow run for that deployment.
Record IDs and timestamps. A valid YAML file or a previous successful manual run
does not establish event delivery. GitHub documents that `deployment_status` is
emitted by deployment status producers; an integration may not create those records.
Do not assume that every Vercel/GitHub integration emits them. No event by the
deadline means trigger liveness is unverified; G3 remains NOT RUN/UNKNOWN, not waived.

If there is no matching deployment record/event, an authorized operator can use
`workflow_dispatch` or the same local trusted bridge after independently checking
the provider's READY deployment for exact S/environment/target. In context choose
`mode: "manual"`, supply a nonempty `manual_reason`, and omit `--event`. The provider
deployment ID and all independent facts remain mandatory; `github_deployment_id`
may be explicitly null when no GitHub Deployment exists. A reason or dispatch input
alone is insufficient. This adapter does not authenticate the operator or poll.
Investigate whether the integration is configured to emit statuses; choose an
explicitly authorized bounded poll/merge-workflow callback later if needed, with
the same identities and liveness reporting. Do not silently create webhooks, tokens,
deployments, repository_dispatch events or scheduled jobs to repair delivery.

## Cancellation, duplicate delivery and target ownership

The inert YAML uses a fixed trusted target concurrency lane and
`cancel-in-progress: false`, so a later docs/evidence push does not request that a
running verification be cancelled through this lane. GitHub's default pending-run
replacement and ordering mean this is not a durable queue or distributed lock.
Include every adopted trigger for the target in the same reviewed lane; other
workflows/providers/local workers remain outside it. Duplicate statuses/manual
fallbacks must consume existing exact-attempt evidence or wait for the verified
owner. The plan adapter provides no deduplication or claim-acquisition mechanism.

Keep a unique attempt ID, owner, S, deployment ID, target, heartbeat and terminal
result in the existing release handoff procedure. Cancellation, timeout or a missed
heartbeat is not proof the worker stopped. Do not dispatch/retry a competing smoke
while termination is unknown; reconcile ownership first. An independently confirmed
terminated attempt may be ABORTED; otherwise retain UNKNOWN/STALE. A later attempt
never erases failures or rebinds old observations to a new SHA.

Deployment Protection, when applicable, requires an existing operator-approved
automation bypass secret and a project-reviewed client/header configuration. Do
not create or reveal a secret. Keep it out of URLs/context/output/artifacts; changing
authentication is not an automatic fallback for failed verification.

Primary references checked for this recipe:

- [GitHub deployment_status events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#deployment_status).
- [GitHub status URL and environment fields](https://docs.github.com/en/rest/deployments/statuses).
- [GitHub concurrency and pending replacement](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).
- [Vercel protection bypass for automation](https://vercel.com/docs/deployment-protection/methods-to-bypass-deployment-protection/protection-bypass-automation).

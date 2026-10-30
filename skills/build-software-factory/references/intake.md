# Adaptive intake

Begin with what is known. For each answer record **confirmed / inferred / unknown**, source, owner and whether it blocks setup or execution. Do not turn this into a form the user must fill entirely.

## First batch when context is absent
- What should the factory deliver, for whom, and what observable result means success?
- Is there an existing repository? Which local folder may be inspected and which may receive the scaffold?
- Which stack and agent harness should it reuse, if any? Is a manual/local-first workflow sufficient?
- What may it do without another approval, and what must remain human-gated?

## Ask only relevant follow-ups
- **Product:** scope/non-goals, representative first work item, deadline, release owner.
- **Context:** architecture, business rules, authoritative docs, environments and existing repo instructions.
- **Overview:** who operates the factory and what decisions need visibility? Reuse existing UI conventions; identify real task, worker, verification, release and optional usage sources. Agree non-secret labels and freshness expectations. Unavailable/stale/proposed data must remain distinct from measured activity. Read [dashboard.md](dashboard.md); default to its usable local read-only snapshot, with separately scoped adapters where the project needs them.
- **Tooling:** installed tools, provider choices and available connectors; verify actual availability. Keep an unverified tool disabled. Ask credential *location/owner*, never credential value.
- **Quality:** inspect existing tests/CI and define G1 production-equivalent smoke plus G2 change-targeted coverage. For greenfield, design a representative non-secret fixture, artifact preparation, observable success/failure assertions and a concrete invocation task before claiming readiness; do not invent commands. Identify the actual web/artifact release target for G3, or an explicitly accepted no-release scope. Stage acceptance/research checks requiring the completed action as post-merge with rationale. Unconfirmed checks remain blocked.
- **Delivery:** deployment target, staging, rollback strategy and who authorizes publication. No deployment target is required for a local scaffold. When work ships (issue fixed or release), should the factory produce a short narrated **done video** (demo of the fix)? Record preference as confirmed/inferred/unknown, scope (which milestones trigger a video) and whether tooling or publication of the video is authorized.
- **Autonomy:** besides kill switch, submitters and rate limits (below), should the factory **continuously scan** a GitHub repository for new issues and auto-pick eligible work (watcher or scheduled routine), or run **one-shot** only when a human or an explicit kickoff starts a pass? Record mode, repository/org scope, eligibility filters and status (confirmed/inferred/unknown). Continuous pickup requires bounded autonomy controls and explicit scheduling authority; default to one-shot when unknown.
- **Data/risk:** real vs fictional data, sensitivity, allowed processing locations, external data-sharing permissions, destructive operations, regulated/high-impact use.
- **Capacity:** monetary ceiling, time ceiling, concurrency, maximum repair attempts, escalation contact and stopping condition. A proposed safe starting policy is no paid execution, one worker and two repair attempts; get project-specific limits confirmed before live use.

## Acting identities and autonomous tools

When relevant, record Git author and authenticated platform account, team/org/repository scope before the first authorized commit. Report mismatches rather than silently changing Git configuration, history or credentials. A binary on PATH is not authentication. Prefer authorized read-only account probes; paid calls and mutations require separate authority.

For autonomous use, record each installed-version headless command, structured-output flag/schema, sandbox/tool restrictions and auth probe/evidence. Establish the kill switch, permitted submitters, rate/concurrency limits and rejection handling. Missing controls block live scheduling. Record issue-intake mode (one-shot vs continuous GitHub scanning) and done-video preference when relevant. Use [operations-config.md](operations-config.md) for optional structured fields.

Resolve ambiguous "latest" inputs by comparing version numbers, source revision and modification times. For conversions, identify the source export and visual acceptance tolerances. Add independent reviewers only when the task warrants their budget and data exposure.

Verify reusable component identity from installed plugin metadata for later upstream feedback. Keep private source identities out of shared provenance. No provenance record grants publication authority.

## Branching
Existing repo: reuse its stack and checks unless the user wants a change. Greenfield: offer a small fitted choice only when needed; do not scaffold an arbitrary framework. High-risk data: keep external workers disabled until boundary and provider approval are settled. Unknown deployment: generate a blocked release handoff, not fabricated pipeline credentials. Explicit 'just show me' request: preview only.

Finish intake with a compact brief and list of unresolved decisions. Ask for approval of the design and write scope together; do not ask the user the same question twice.

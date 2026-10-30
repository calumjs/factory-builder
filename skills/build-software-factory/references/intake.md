# Intake questions

Record each answer as **confirmed / inferred / unknown** with its source, owner and whether it blocks setup or execution; store the ones that matter in `config.assumptions` ([operations-config.md](operations-config.md)). Unknowns stay visible — a disabled draft needs no invented confirmation. Finish with a compact brief and the unresolved decisions, and ask for design approval and write scope together.

## First batch (when context is absent)
- What should the factory deliver, for whom, and what observable result means success?
- Is there an existing repository? Which folder may be inspected, and which may receive the scaffold?
- Which stack and harness should it reuse? Is a manual, local-first workflow enough?
- What may it do without another approval, and what stays human-gated?

## Follow-ups, only where relevant
- **Product:** scope and non-goals, a representative first work item, deadline, release owner.
- **Context:** architecture, business rules, authoritative docs, environments, existing repository instructions.
- **Overview:** who operates the factory and which decisions need visibility; real task, worker, verification, release and usage sources; non-secret labels and freshness expectations ([dashboard.md](dashboard.md)).
- **Tooling:** installed tools, providers, connectors — verify availability; an unverified tool stays disabled. Ask where a credential lives and who owns it, never its value.
- **Quality:** existing tests and CI; the G1 production-equivalent smoke and G2 change-targeted designs; for greenfield, the fixture, artifact, success/failure assertions and the task to implement the invocation. The actual G3 target, or an accepted no-release scope. Which acceptance/research checks need the completed action (post-merge, with rationale).
- **Delivery:** deployment target, staging, rollback, who authorizes publication (none is required for a local scaffold). Whether shipped work gets a narrated done video, which milestones trigger it, and whether tooling or publication is authorized ([done-videos.md](done-videos.md)).
- **Autonomy:** one-shot (default when unknown) or continuous issue pickup; repository scope and eligibility filters. Continuous means around-the-clock polling or event-driven coverage; ask about a window only if the operator wants one, and record its timezone and evidence. Continuous needs bounded controls (kill switch, allowed submitters, rate limit) and scheduling authority.
- **Data and risk:** real vs fictional data, sensitivity, allowed processing locations, external sharing, destructive operations, regulated use.
- **Capacity:** cost ceiling, time ceiling, concurrency, repair attempts, escalation contact, stopping condition. Proposed safe start: no paid execution, one worker, two repair attempts — confirm before live use.

## Identities and headless tools
- Record the Git author and the authenticated platform account, team and repository scope before the first authorized commit; report mismatches rather than changing config, history or credentials. A binary on PATH is not authentication; prefer an authorized read-only probe.
- For autonomous use, record each installed-version headless command, structured-output flag, sandbox and tool restrictions, and authentication evidence. Missing controls block live scheduling.
- Resolve an ambiguous "latest" input by showing candidates with version, revision and modified time. For conversions, identify the source export and visual tolerances. Add independent reviewers only when the task warrants their budget and data exposure.
- Record the builder's identity from installed plugin metadata for later upstream feedback; keep private source identities out of shared provenance.

## Branching
Existing repository: reuse its stack and checks unless the user wants a change. Greenfield: offer a small fitted choice only when needed. High-risk data: keep external workers disabled until boundary and provider approval are settled. Unknown deployment: a blocked release handoff, not invented credentials. "Just show me": preview only.

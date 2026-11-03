# Intake questions

Record each answer as **confirmed / inferred / unknown** with its source, owner and whether it blocks setup or execution; store the ones that matter in `config.assumptions` ([operations-config.md](operations-config.md)). Unknowns stay visible — a disabled draft needs no invented confirmation. Finish with a compact brief and the unresolved decisions, and ask for design approval and write scope together.

## First batch (when context is absent)
- What should the factory deliver, for whom, and what observable result means success?
- Is there an existing repository? Which folder may be inspected, and which may receive the scaffold?
- Which stack and harness should it reuse? Is a manual, local-first workflow enough?
- What may it do without another approval, and what stays human-gated?

## Follow-ups, only where relevant
- **Existing automation:** inspect permitted agent/bot workflow and configuration sources, trigger/state labels and owners; record an explicit coexist, replace or wrap decision using the [automation inventory](headless-intake-preflight.md#inspect-existing-automation-before-proposing-another-loop). Unresolved overlap keeps the proposed path inactive; inventory changes no other tool or settings.
- **Product:** scope and non-goals, a representative first work item, deadline, release owner.
- **Context:** architecture, business rules, authoritative docs, environments, existing repository instructions.
- **Overview:** who operates the factory and which decisions need visibility; real task, worker, verification, release and usage sources; non-secret labels and freshness expectations ([dashboard.md](dashboard.md)).
- **Tooling:** installed tools, providers, connectors — verify availability; an unverified tool stays disabled. Ask where a credential lives and who owns it, never its value.
- **Quality:** existing tests and CI; the G1 production-equivalent smoke and G2 change-targeted designs; for greenfield, the fixture, artifact, success/failure assertions and the task to implement the invocation. The actual G3 target, or an accepted no-release scope. Which acceptance/research checks need the completed action (post-merge, with rationale).
- **Delivery:** deployment target, staging, rollback, who authorizes publication (none is required for a local scaffold). Whether shipped work gets a narrated done video, which milestones trigger it, and whether tooling or publication is authorized ([done-videos.md](done-videos.md)).
- **Autonomy:** one-shot (default when unknown) or continuous issue pickup; repository scope and eligibility filters. Continuous means around-the-clock polling or event-driven coverage; ask about a window only if the operator wants one, and record its timezone and evidence. Continuous needs bounded controls (kill switch, allowed submitters, rate limit) and scheduling authority.
- **Data and risk:** real vs fictional data, sensitivity, allowed processing locations, external sharing, destructive operations, regulated use.
- **Checks that write data:** for a web target with a database, will G3 and video checks be read-only, use explicitly authorized run-scoped writes with teardown, or use an authorized disposable representative target? Name the actual target, fictional fixtures, cleanup owner and allowed delete scope; record data written, cleanup and residue as described in [disposable-fixture-example.md](disposable-fixture-example.md). A preview result does not satisfy a required production check; missing safe setup stays BLOCKED/NOT RUN, while optional checks remain WAIVED with their observations.
- **Capacity:** cost ceiling, time ceiling, concurrency, repair attempts, escalation contact, stopping condition. Proposed safe start: no paid execution, one worker, two repair attempts — confirm before live use.

## Identities and headless tools
- Record the Git author and the authenticated platform account, team and repository scope before the first authorized commit; report mismatches rather than changing config, history or credentials. A binary on PATH is not authentication; prefer an authorized read-only probe.
- For autonomous use, record each installed-version headless command, structured-output flag, sandbox and tool restrictions, and authentication evidence. Missing controls block live scheduling.
- Resolve an ambiguous "latest" input by showing candidates with version, revision and modified time. For conversions, identify the source export and visual tolerances. Add extra reviewers or panels beyond the default single independent reviewer only when the task's risk, budget and data exposure warrant them.
- For a new interviewed factory, recommend [supplied code-review records and Q1](code-review.md) using `assets/example-review-config.json`: one required approval, independent review, and no distinct-provider requirement. Reuse known preferences; ask only consequential missing questions about reviewer availability, applicable lenses, budget/data boundaries and optional inversion for the change's risk. An explicit zero/optional choice retains `record_schema: 1` and sets `required_approvals: 0`, keeping Q1 visibly WAIVED with its recorded result; record the choice, rationale and source in the existing setup assumptions/proposal. Do not silently omit review or turn unavailable required review into a waiver. Legacy config absence and existing factories remain unchanged until a separate explicit migration. Do not infer provider execution or spending authority from the choice.
- Record the builder's identity from installed plugin metadata for later upstream feedback; keep private source identities out of shared provenance.

## Branching
Existing repository: reuse its stack and checks unless the user wants a change. Greenfield: offer a small fitted choice only when needed. High-risk data: keep external workers disabled until boundary and provider approval are settled. Unknown deployment: a blocked release handoff, not invented credentials. "Just show me": preview only.

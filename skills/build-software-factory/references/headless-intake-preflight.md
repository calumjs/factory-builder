# Headless helper and existing-automation preflight

Use this before assigning factory commands to an existing CI worker or unattended
harness. It is a preparation checklist, not a workflow installer or permission to
launch another agent. The generated [launch guide](../assets/templates/launch-guide.md)
still governs source identity, tool availability, trust and scoped execution.

## Interpreter and trusted helper availability

The current scripts use sibling imports and **do not support Python `-I` isolated
mode**. For example, `python -I scripts/scaffold.py --help` fails importing
`research` before argument parsing. `-B` prevents bytecode writes; it does not
provide isolation. If the harness requires `-I`, keep the affected command and its
checks BLOCKED. Do not remove that requirement, inject an import path, change a
wrapper or select another launch route to bypass it. Support for that mode would
need a separately reviewed implementation compatible with the harness policy.

When ordinary script invocation is permitted, a headless worker can use a trusted
existing builder checkout or verified package without an interactive plugin host.
This is a source-distribution choice, not authorization to obtain or install it:

1. Record the approved Python 3.9+ executable's **absolute path**, version and exact
   intended argv. A PATH name or command existing on another machine is insufficient.
2. Identify the builder's actual source/package path and immutable full revision,
   plus any dirty-tree or packaging differences. Reuse the launch guide's trusted
   inventory verification; a version string alone is not identity. Keep trusted
   helper code outside the untrusted PR checkout, and preserve the verified sibling
   modules. A relative `scripts/status.py` may accidentally name project code.
3. Verify that the required helper files exist under that exact trusted skill root.
   Depending on the task, these include `scripts/scaffold.py`, `status.py`,
   `gates.py`, `run.py`, `scoped_assessment.py`, `incremental_records.py` and
   `observation_drafts.py`. Do not infer availability from dashboard files:
   the copied dashboard bundle intentionally omits the status and Run writers.
4. Within already granted local execution scope, check each needed command's
   `--help` with the actual interpreter and **absolute helper path**, from the
   worker's intended working directory. An illustrative argument vector is
   `["<approved-python>", "-B", "<trusted-skill-root>/scripts/status.py", "--help"]`.
   Pass literal argv, not shell-built request text. This checks launch/import and
   interface availability only; it runs no application tests and proves no hosted
   authentication, permissions or future worker availability.
5. Record the checked helper identities, argv and results in the external task
   handoff. Missing tools, unsupported invocation or a denied command remain
   BLOCKED; hand off the missing provisioning/authority decision to the owner.
   Do not install a plugin, download helpers, copy PR-supplied code into a trusted
   location, widen settings or fabricate a status event as a fallback.

With verified tooling and separate evidence-write authority, use the existing
[task/gate recording procedures](incremental-workflow.md) and
[observation draft/export flow](observation-drafts.md). These record supplied
observations; they do not execute the check or make its evidence true. Preserve
subject versus storage identities and failed history. A PR-body note may be a
referenced observation when appropriate, but does not replace required structured
task/gate records or turn missing automated checks into PASS.

The [inactive CI adapter](../assets/templates/ci/README.md) is the assessment path
after records exist. It is not a worker installer, dispatch engine or evidence
writer. Do not claim CI integration from a successful local `--help` probe.

## Inspect existing automation before proposing another loop

Within the repository read scope, inventory existing agent/bot delivery automation:
workflow files under `.github/workflows` (or the project's actual CI directory),
named agent configuration folders, checked-in scripts, repository instructions and
documented state/trigger labels. Follow relevant local references within scope;
do not run scripts, read credential values or assume a particular tool's folder
name. If separately authorized metadata reads are available, corroborate current
workflow/label/routine state. Checked-in configuration alone is not proof a loop
is enabled or that an actor has a particular permission.

For each discovered loop, record source path and revision, owner, trigger/event,
issue/label scope, actor identity used for admission, outputs, state transitions,
stop control, known shared resources and current evidence/unknowns. Distinguish the
issue author from the actor applying a label. A role name, label or provider claim
does not establish action authority. Review the overlap explicitly:

| Decision to record | Questions for the owner before any activation |
|---|---|
| Coexist | Are trigger scopes disjoint? Who admits overlapping work and prevents duplicate writes? |
| Replace | Who owns the old loop, its pending work and the separately authorized stop/adoption plan? |
| Wrap | Which loop owns admission, retries, state and output? How are duplicate events reconciled? |
| Unresolved | What evidence or owner decision is missing? Keep the proposed overlapping path inactive. |

Record the chosen decision, rationale, owner, evidence and unresolved dependencies
in the accepted brief or approved external operating record. Preserve the other
tool unchanged during intake: no label creation, workflow edits, disabling,
schedule changes or settings changes follow from this checklist. A local lock or
state label alone does not establish cross-worker exclusion.

## Research IDs and setup versus per-item assessment

`R` IDs follow the order of **selected** practices in `research.practices`, starting
at R1. Candidate/rejected practices do not consume an R number; the practice ID's
spelling is unrelated. Generated `verification.md` already shows `R1 / P7`-style
mapping beside its planned checks. Review that mapping before setting
`operations.smoke_gates.check_stages`; do not assume P7 maps to R7.

| Synthetic practice, in stored order | Decision / phases | Generated gate and default stage |
|---|---|---|
| P2 | candidate / intake | No R row |
| P7 | selected / intake, release | R1, pre-merge |
| P12 | selected / build, verify | R2, pre-merge |
| P20 | selected / release | R3, post-merge |

Changing selected order or decisions can change R identities. Review mappings and
any stage overrides together in a selective contract update; never carry an old
observation onto a newly numbered practice automatically. A stage override answers
**when** the check applies, not whether it is setup-only or optional.

For example, let T1/A1/R1 describe accepted watcher setup and T2/A2/R2 describe an
accepted per-item change. Keep setup evidence on its actual setup subject, and
retain meaningful dependency links. Review whether this item changes the watcher,
its policy, tooling or assumptions; if so, include the affected setup checks or
leave the scope unresolved. Do not add a fictitious "local run, not applicable"
result merely to avoid a still-required check.

After the owner has accepted this **specific** per-item assessment scope, a
synthetic scope file outside the factory could contain:

```json
{"purpose":"Accepted per-item view; setup assessed separately","gates":["A2","R2"],"tasks":["T2"]}
```

Run the trusted existing helper with the actual record copy and subject:

```text
python <trusted-skill-root>/scripts/scoped_assessment.py --factory <factory> --scope <approved-scope.json> --stage pre-merge --revision <actual-item-subject>
```

Use the approved absolute interpreter in place of `python`. The helper includes
G1/G2 and the selected tasks' acceptance IDs automatically, checks selected-task
evidence against the exact supplied subject, and reports excluded rows. It checks
dependency completion, but a historical `done` state does not independently attest
that setup remains valid. **Excluded is not WAIVED or PASSED.** A scoped eligible
result may coexist with project-wide BLOCKED readiness and cannot authorize a
release. Assess whole-project requirements separately; the operator's explicit
optional choices remain waivers with their underlying observations.

This uses the existing [scoped-assessment contract](incremental-workflow.md), not a
new setup lifecycle. It neither classifies setup automatically nor carries old
evidence forward. Daily/in-flight admission, role-based submitters, periodic spend
limits and repository-file research sources require separate designs; this guide
does not encode them in free text or imply they are enforced.

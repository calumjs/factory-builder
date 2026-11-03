# Supplied code review and optional inversion

This opt-in workflow gives Verify a structured output and a dedicated Q1 pre-merge
process row. It checks supplied records, not actual reviewer execution, identity,
independence, model/provider provenance, artifact inspection or authority. It does
not call providers, approve GitHub PRs, install hooks, read harness logs, execute
review commands, merge, deploy or spend.

## Choose it deliberately

New setup may select `assets/example-review-config.json`, adapting its project
choices before scaffolding. The optional operations patch is:

```json
{"review":{"record_schema":1,"required_approvals":1,"independent":true,"distinct_providers":false}}
```

Absence of `record_schema` preserves legacy controls and gate behavior. Explicit
zero approvals creates optional Q1; a positive count creates required Q1. No fixed
number of agents or providers is imposed. Spec, Standards and Correctness are
coverage lenses; Security and Architecture are selected when applicable. The
generated `review-guide.md` gives the procedure and is explicitly routed from the
opted-in Verify and Release guides. Existing skill templates remain unchanged.

For an existing factory, preview a separate review-only update:

```sh
python scripts/update_operations.py --factory <factory> --operations <review-patch.json> --review-workflow
```

Inspect the exact diff and digest before using the separately authorized
`--apply --approve-plan <digest>`. Adoption recognizes a complete current or known
v1.36 operations/gates/dashboard consumer set, captures unchanged dependencies,
adds the review parser and research validator, and refuses mixed/customized copies.
Older factories first need their own reviewed compact-phase/runtime migrations.
Unknown/custom phase entrypoints, guides, parser or dependencies are preserved by
refusal. This does not claim every older reader fails closed: older gates can
ignore Q1 or its typed evidence. Use the compatible installed/copied consumer set.

Only Q1 is added/reset; unrelated raw row content, requiredness and history remain.
Later review-policy updates also need `--review-workflow`; existing editable Q1
requiredness is preserved. Changing approval count alone does not revoke a user's
existing row waiver. A manually required zero-approval Q1 still needs at least one
approval; it never passes vacuously. Optional runtime receipts remain available
with `--migration-receipt`, including newly added runtime dependencies. They are
runtime transition records, not whole-factory provenance or atomic success claims.

## Capture a real supplied round

Read the current calculation and selected-round token without writing:

```sh
python scripts/review_records.py --factory <factory>
```

`policy_sha256` is SHA-256 of UTF-8 canonical JSON (`sort_keys=True`,
`ensure_ascii=True`, compact separators, no newline, finite JSON values) containing
exactly `controls`, `budget`, `acceptance`, and validated `research`. Controls are
the normalized current policy controls. JSON object formatting/order is irrelevant;
array order remains significant. Acceptance/research changes, including research
metadata-only changes, conservatively invalidate prior review. This is not proof
that every external input is unchanged or that supplied provenance is authentic.

The handoff contains one uniquely marked version-1 JSON section:

````text
<!-- factory-review-record:v1:start -->
```json
{"schema_version":1,"selected_round":null,"rounds":[]}
```
<!-- factory-review-record:v1:end -->
````

The outer `text` fence above is illustration only; the actual marked section must
not be hidden in another fence/comment. The initial empty section makes no review
claim. All keys below are required; extra/duplicate keys and unsupported versions
are refused. Strings are supplied non-secret labels/references, never fetched.

| Record | Fields |
| --- | --- |
| Round | `id`, `subject`, `base`, `policy_sha256`, `artifact`, `risk`, `builder`, `required_lenses`, `applicability_reason`, `inversion`, `reviews`, `resolutions` |
| Artifact | `kind` = `source_diff`, `sha256` = lowercase 64-hex digest of the exact approved source/diff artifact, `reference` |
| Builder | `identity`, `provider`, `model_family`; unknown values are explicit `null`, never inferred |
| Inversion choice | `choice` = `not_selected`, `selected`, or `waived`; concrete `reason` and named `decided_by` |
| Reviewer | `id`, `reviewer`, `role`, `subject`, `base`, `artifact_sha256`, `provider`, `model_family`, `independent`, `inputs`, `verdict`, `observed_at`, `evidence`, `lenses`, `findings` |
| Finding | `id`, `severity`, original `claim`, original `evidence`, `verification` |
| Finding verification | `null`, or a distinct `reviewer`, `disposition`, `evidence`, and `reason` |
| Prior-finding resolution | `round_id`, `review_id`, `finding_id`, distinct `reviewer`, `disposition`, `evidence`, `reason` |

Use unique bounded IDs (letters/digits plus `_ . : @ / -`), not display-name aliases
to inflate counts. `subject` and `base` identify exact supplied source revisions;
all reviewer records must repeat those values and the exact artifact digest. Full
Git IDs are appropriate for Git subjects; the checker never resolves prefixes or
fetches repositories. `risk` is low/medium/high. `required_lenses` includes spec,
standards, correctness and applicable security/architecture; each reviewer lists
the lenses actually covered. A reviewer is counted once, regardless of lenses.

Roles are primary, inversion or additional, with at most one primary/inversion.
Verdicts are approve, request_changes or blocked. Timestamps use a real calendar
date/time with explicit timezone and cannot be future observations. Provider and
family may be `null`; unknown/unconfirmed placeholders cannot prove constraints.
`independent` is a supplied boolean; `inputs` is source_only or shared_context.
Evidence is an explicit approved report/reference, not a claim inferred from an
empty field. Severity is critical, major or minor. Verification dispositions are
confirmed, refuted, resolved or unconfirmed. Critical/Major findings remain blocking
unless a separate checker supplies concrete refuted/resolved evidence. Unconfirmed
findings are retained as unconfirmed, never downgraded into approval by omission.

`resolutions` explicitly references prior unresolved Critical/Major findings for
the **same subject and base**. A new approval with no findings cannot erase them.
Unknown, duplicate-in-round, future, already-closed or cross-subject/base references
are refused. Confirmed/unconfirmed remains blocking; only a distinct checker's
concrete refuted/resolved disposition closes that reference. Original claims remain
unchanged. Other-subject/base findings remain visibly historical and unresolved in
the context helper; fresh approval does not assert their repair. Cross-subject
continuation/resolution is outside this first schema, not inferred from shared base.

Append one complete round JSON object through the existing reviewed record writer:

```sh
python scripts/incremental_records.py --factory <factory> --kind review --input <round.json>
```

The preview writes nothing. After reviewing its diff/digest, the explicitly
authorized apply appends the round and explicitly selects it. Existing rounds and
finding claims are immutable; duplicate IDs and history rewrites are refused. The
local CI evidence adapter also requires storage history to retain the exact review
round prefix from its explicitly selected subject snapshot. These checks do not
authenticate edits made outside the supplied writer or establish distributed history.
The selected round must be the final appended record, not whichever verdict is newest
by timestamp or most favorable. Old-subject assessment uses its historical snapshot.
A later disagreement cannot be bypassed by selecting an earlier approve.

Read the context helper again for `selected_round.evidence_token` and
`artifact_target`. Separately record Q1 with the ordinary gate writer: evidence is
`review:<round-id>:<canonical-ledger-SHA256>` and target is
`sha256:<supplied-artifact-SHA256>`. Supply the actual observation time, exact subject,
environment and manual/zero exit observation. Q1 time must follow the supplied
reviewer verdicts. Typed content, policy, subject, token and target must agree.
The token hashes the complete canonical section object, including historical
rounds and explicit selection, so prior data used by assessment is also bound.
Arbitrary freeform "approve" text cannot satisfy Q1. The two record writes are
separate single-file transactions; intermediate or stale state remains blocked.

## Optional inversion and verdicts

For a selected inversion, give the second reviewer source/diff/spec independently,
without the first review, implementer's reasoning or implementer's evidence package.
Its supplied identity differs from the known builder, inputs are source_only, and
its known model family differs from the BUILDER family. Different provider/harness
names alone do not prove a different family. Distinct-provider policy is checked
separately across approvals. These remain consistency checks on claims, not proof.

| Supplied state | Required Q1 consequence |
| --- | --- |
| All selected reviewers approve, sufficient unique approvals/coverage and resolved findings | Can satisfy review consistency with matching Q1 observation |
| Both request changes | Block; return to Build |
| Approve and request_changes disagree | Block and escalate with both findings; no automatic tie-break |
| Required reviewer blocked/missing, or required provenance unknown | Block; no automatic waiver or paid fallback |
| Optional inversion explicitly waived with named decision/reason | Visible inversion WAIVED; primary/count/independence/provider requirements still apply |
| Q1 explicitly optional | Q1 WAIVED with recorded result; well-formed section still required, no fabricated reviewers |

An inversion pair is one recorded round. Set explicit project round/time/cost limits
before work and stop at them; this helper does not enforce scheduling or spending.
Limits bound parsing/history: 2 MB handoff, 1 MB section, 256 rounds, 16 reviewers
per round, 64 findings per reviewer, 2,000-character evidence text, 128-character IDs,
256 resolutions per round, 256-character subject/base, and a 256 KiB writer input. Exceeding history capacity
refuses rather than trimming; deliberate archival needs a separately reviewed design.
No actual provider call, approval, deployment, privacy export or hook follows from
this workflow. Conflicting structured handoffs remain outside automatic #78 merges.

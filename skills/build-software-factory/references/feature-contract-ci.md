# Optional feature-contract CI check

This installed pre-merge check composes with `ci_evidence.py`: missing policy-required
issue-linked additions make that command fail, even when its recorded gates otherwise
satisfy their requirements. It does not execute G0/G2, write PASS/WAIVED evidence, create
a workflow or require a hosted check. Adopting and requiring the job is a separate,
explicit project decision. Existing commands without the four feature flags behave as
before; the existing `change_contract.py` mapper still permits legitimate reuse.

## Choose the project rule and its trusted inputs

An operator selects the rule before applying it to a change. Keep the UTF-8 policy
outside the change checkout, and supply its raw SHA-256 through an independently
accepted channel. A digest calculated from an untrusted PR policy does not confer trust.
Do not let the PR choose its own weaker policy or omit the mandatory flags in an adopted
job. The exact version-1 schema has no optional or extra fields:

```json
{"version":1,"acceptance_delta":"added","task_delta":"added_or_changed"}
```

`acceptance_delta` is `reuse` or `added`; `task_delta` is `reuse`, `added` or
`added_or_changed`. For **each supplied closing issue**, each non-reuse dimension needs
at least one qualifying mapped ID. The example requires an appended criterion and a
new or changed mapped task. `reuse` requires a valid mapping but no new definition in
that dimension. These are deliberate project choices, not universal requirements.

Acceptance IDs are positional. For a feature with closing claims, the entire base
acceptance list must remain an exact prefix of the subject list, including when the
policy permits reuse. Old-criterion edits, deletions and reordering are unsupported;
do not rename them into an apparent addition. Use the existing [acceptance planner](acceptance-planning.md)
and [inactive candidate/recovery workflow](acceptance-candidates.md) for reviewed
append-only updates. A broader criterion rewrite requires separate identity review,
not a silent rebaseline or a fabricated evidence-only follow-up.

Task IDs are stable within these supplied snapshots. A task definition includes every
task property except living `status`; plan-level events are not task-definition
changes. JSON property order is immaterial. List order remains significant, including
dependencies, acceptance links and allowed paths. Added/changed definitions are only
structural observations: duplicating wording, cosmetic edits or changing boundaries
does not prove new behavior is covered. An operator must review the actual diff and
meaning; no heuristic labels a change as feature, maintenance, docs-only or evidence-only.

## Bind base, tested subject and evidence storage

Keep a reviewed request outside the checkout. Its `contract` is the existing mapper's
version-1 contract; preserve its explicit rationale and exact subject. In this adapter,
issue references use lowercase `owner/repository#positive-number`, not URLs or titles.
References are supplied claims, never dereferenced. Example shape (replace placeholders):

```json
{"version":1,"base":"<full-base-commit-sha>","subject":"<full-tested-subject-sha>",
 "closing_issues":["owner/project#123"],
 "contract":{"version":1,"subject":"<full-tested-subject-sha>",
   "classification":"feature","rationale":"Reviewed new archive behavior",
   "issues":[{"reference":"owner/project#123","tasks":["T2"],"acceptance":["A2"]}]}}
```

The request's base/subject must equal the explicit CLI identities. Base must be an
already available ancestor of the tested subject; no merge-base is inferred. Both
committed config/task snapshots are read through verified Git object bytes with bounds,
regular-file/tree checks and fetch transports disabled. Missing, malformed or unsupported
history is an error even for maintenance or no-closing-issue claims. Unrelated linked
entries in traversed trees may require separate review under this conservative reader.

`--storage` remains the existing clean checkout containing evidence about `--subject`.
It can equal the subject or be a permitted evidence-only descendant. Its factory
definitions must match the subject; storage may not smuggle scope changes into evidence.
The feature comparison is **base to tested subject**, never base to evidence storage.
The request is external so recording its subject does not create a self-referential commit.
No short-SHA equivalence, squash/merge equivalence or tree-equality evidence transfer is
assumed. Fresh subjects require reviewed fresh request and actual evidence as usual.

`maintenance` requires the existing rationale; no-closing-issue feature claims still
need the mapper's valid nonempty mappings. Both produce `outside_trigger_claim`, not
coverage or PASS. A maintenance claim may include mapped closing issues, but explicitly
remains an operator-classified exemption. The caller is responsible for supplying all
closing claims and reviewing the classification. Empty lists are not automatic proof
of no claims. Ordinary evidence and gate requirements still apply in every case.

## Inactive job recipe

Use an approved actual interpreter and trusted installed builder helper pinned outside
the PR checkout, as in the existing `ci/job.example.py`. Confirm those paths/tools and
the exact local commits exist; do not install, fetch or substitute fabricated results.
The optional environment extension to that **inert** template is:

```text
FACTORY_PYTHON=<approved-absolute-python-path>
FACTORY_TRUSTED_HELPER=<trusted-pinned-builder>/scripts/ci_evidence.py
FACTORY_REPO=<clean-evidence-storage-checkout>
FACTORY_TESTED_SUBJECT_SHA=<full-tested-subject-sha>
FACTORY_EVIDENCE_STORAGE_SHA=<full-storage-sha>
FACTORY_STAGE=pre-merge
FACTORY_FEATURE_POLICY=<external-reviewed-policy.json>
FACTORY_FEATURE_POLICY_SHA256=<independently-accepted-raw-policy-sha256>
FACTORY_FEATURE_REQUEST=<external-reviewed-request.json>
FACTORY_FEATURE_BASE_SHA=<full-base-sha>
```

Existing target/task requirements and `FACTORY_DIRECTORY` remain available. The template
builds an argv list without a shell and propagates the helper exit status. Its equivalent
additional arguments are `--feature-policy`, `--feature-policy-sha256`,
`--feature-request`, and `--feature-base`. All four are required together and only for
pre-merge. Never execute a PR-supplied helper/job wrapper in a privileged workflow.
An existing generated job needs separate reviewed adoption; nothing upgrades it implicitly.

The helper returns 0 only when the composed recorded requirements are satisfied
(including explicitly reported waivers), 1 when required evidence or feature policy is
blocked, and 2 for invalid/unavailable inputs. `feature_check` reports the chosen policy,
exact base/subject, raw policy/request digests, mapper digest and numbered per-issue
delta counts/reason codes. Issue positions correspond to the private request list.
It withholds issue references, definition text, local paths and rationale; treat digests
and identities as potentially sensitive too. Keep reports in an approved private store.
Inputs are bounded, read-only and rechecked for ordinary concurrent changes. No files,
Git refs, manifests, gates, remote services or settings are changed.

Local synthetic CLI tests demonstrate composition and refusal, not live CI activation,
application coverage or authentic test execution. Before relying on a hosted required
check, separately review its trusted adapter, completeness of supplied claims, policy
provenance, permissions and actual job result for the exact subject.

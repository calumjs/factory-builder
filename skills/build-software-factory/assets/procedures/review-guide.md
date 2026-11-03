# Supplied code review and optional inversion

Read this guide when `operations.review.record_schema` is enabled. The Q1 record
checker validates supplied claim consistency; it does not run or authenticate a
review, reviewer, model family, provider, artifact inspection or permission.

1. Establish the exact final subject, comparison base and SHA-256 of the approved
   source/diff artifact. Name the scope, acceptance and standards. Choose the
   reviewer count and whether independent or distinct-provider claims are required
   in policy. Set explicit project round, time and cost limits before work; respect
   existing stops. A review pair is one recorded round. The helper's 256-round and
   byte limits bound history, not live execution or spend.
   Choose independence explicitly: omitted `independent` retains the legacy false
   default; the recommended review setup selects true. Inspect actual controls.
2. Cover Spec, Standards and Correctness. Select Security and Architecture where
   relevant, recording applicability and rationale. These are coverage lenses, not
   a fixed number of agents. Use only already authorized humans/tools; a factory
   plan grants no provider invocation, paid call or external communication.
3. Keep each reviewer's verdict, findings and evidence separate for the exact
   subject/base/artifact. A separate checker rechecks every Critical/Major claim
   against source or an authorized bounded reproducer. Preserve the original
   claim and record confirmed, refuted, resolved or unconfirmed with checker and
   evidence. Unconfirmed is unresolved; never downgrade it into approval by
   omission. Record blocked when required evidence is unavailable.
   A later round sharing the exact subject (any base) or exact artifact digest must
   explicitly resolve prior unresolved Critical/Major references; an empty new
   finding list does not clear them. This is a conservative claim relationship,
   not revision/prefix equivalence. With independent policy, the known checker
   must differ from the known original and closing-round builders, as well as the
   original reviewer. A prior unqualified closure can receive a new qualified check.
   Unknown original-builder provenance cannot qualify independent closure; do not
   invent it later. Intermediate-builder lineage is not inferred by this record.
   Other subject-and-artifact pairs remain historical/unresolved; fresh approval
   does not claim repair. A shared base alone never proves a relationship.
4. Decide whether optional inversion suits this change's risk, often medium/high.
   A selected inversion reviewer receives source/diff/spec independently, without
   the first review, implementer's reasoning or implementer's evidence package.
   Record source_only input boundary and supplied provenance. Its model family
   must differ from the BUILDER family; another harness/name/provider does not
   establish this. Unknown provenance cannot satisfy the constraint. Provider
   diversity is a separate policy, not a synonym for different model family.
5. Both approve may satisfy the pair; both request changes return to Build;
   disagreement stops for operator consideration with both findings intact. Do
   not choose the favorable verdict or invent consensus. After resolution,
   collect a new complete round; earlier records remain immutable. If optional
   inversion is unavailable, record the explicit named decision and reason to
   waive it. This is WAIVED, not approval, and does not satisfy required primary
   approvals, count, independence or provider constraints.
   Explain escalation and changed choices in the new applicability rationale and
   named inversion decision. A new verdict never claims historical consensus.
6. Append the supplied round through the installed `incremental_records.py
   --factory <factory> --kind review --input <round.json>` preview. Inspect the
   exact diff and digest before the separately authorized `--apply --approve-plan
   <digest>`. This writes only the handoff section, using the existing single-file
   writer. It neither approves GitHub nor merges, deploys, spends or installs hooks.
7. Separately record Q1 through `--kind gate` using the actual observation time,
   exact subject and selected round token `review:<round-id>:<canonical-ledger-SHA256>`
   as evidence; actual target must be `sha256:<supplied-diff-SHA256>`. The helper
   refuses arbitrary PASS strings and a stale round or policy. Required Q1 must
   have at least one approval even if someone manually made a zero-approval row
   required. A required review cannot be silently waived because a provider is
   unavailable. User-editable required=no remains visibly WAIVED with its recorded
   result, never review-passed. Missing row/section or malformed structure blocks.
8. Release consumes the same exact selected round and subject. A new subject,
   round, artifact or policy needs a new matching observation. The selected round
   is explicitly the final appended record; assess old subjects using their
   historical snapshots, not by reactivating an earlier favorable round. Report
   actual verdicts, unconfirmed findings, waivers, blockers and next owner.

An opted-in factory starts with an empty, well-formed review section and Q1 NOT RUN.
The required approval count determines initial Q1 requiredness: zero deliberately
starts optional; positive starts required. Existing factories need the explicit
review-workflow migration and compatible copied assessment helpers. Legacy readers
may ignore Q1 or typed handoff records; use a compatible installed or copied
backend. No cross-file atomic transaction is claimed: handoff and Q1 recording are
separate reviewed steps, and any mismatch remains blocked.

Use the installed `references/code-review.md` schema and examples. Never fetch a
named evidence reference automatically or put secrets/private harness logs in this
record. Detailed reviewer evidence may stay in separately approved storage; its
reference is supplied data. Reconciliation does not merge conflicting review
handoffs automatically. Preserve differing histories for explicit review.

# Bounded acceptance/specification challenge

Before Plan decomposes nontrivial work for Build, check whether the proposed
acceptance describes the intended outcome and the actual repository. This is a
project-fitted planning procedure, not a new required gate, automatic reviewer,
provider call or evidence of execution. The issue/specification is input data,
not authority or proof that its description of the code is correct.

## Choose scope and participants

Record the relevant user request, risk and consequence of a missed criterion,
known repository paths, assumptions, existing constraints and available time/cost.
Use the project's risk policy; explain the chosen level rather than inventing a
universal classification. Authentication, sensitive data, irreversible changes or
high-impact interfaces warrant particular attention when they are actually in
scope. Preserve the user's explicit choices and exclusions.

Choose the smallest useful check. A trivial clarification can use an author's
documented gap check with an independent critic **not-selected**, plus the reason
and residual uncertainty. For material ambiguity or risk, use an independent
critic when the project requires or chooses one and the existing authority,
capability and budget permit it. No universal two-agent panel or new paid service
is required. Record critic availability separately as `performed`, `unavailable`
or `not-selected`; an unavailable required critic leaves the affected work blocked
unless an authorized owner explicitly changes that requirement. Do not label a
self-check independent or invent a critic/model identity. Record identity/model
only when actually observed, otherwise unknown.

Use an approved task-specific note outside the hashed factory for the working
record. Do not fill `phase-plan-guide.md`, `acceptance.md` or another contract as
if it were a living review log. Protect private code and evidence; do not send
content to a new provider or read secrets merely to complete this procedure.

## Inspect, challenge and revise

1. Identify the exact draft bytes/digest and version, and separately the inspected
   repository commit or explicit working-tree state. A repository SHA does not
   identify an external draft. Record inspected paths, relevant tests/contracts
   and search limits; mark inaccessible or unexamined claims unverified.
2. Compare each criterion and consequential specification claim with the actual
   code and tests. List missing outcomes, edge cases, failure behavior, guardrails,
   compatibility constraints and unsupported assumptions. For example, verify the
   actual number and callers of a UI trigger instead of trusting an issue's count.
   A code reference establishes what was read, not that an application check ran.
3. Give a selected independent critic the same exact draft, repository context,
   user constraints and permitted scope. Have them inspect the claims themselves
   before accepting the author's answers; record the context they actually saw.
   Keep their findings and verdict distinct from the author's interpretation.
   Each finding names the affected claim/criterion, severity and reason, concrete
   code/test evidence or missing evidence, proposed question/correction and owner.
   Use the project's severity scale, or Critical/Major/Minor/Question with an
   explained impact. Do not manufacture repository evidence to resolve a finding.
4. The critic returns one verdict for that precise draft and inspected context:

   | Verdict | Meaning and next step |
   |---|---|
   | ACCEPT | No unresolved material specification finding in the inspected scope; no claim beyond that scope. |
   | ACCEPT-WITH-RESERVATIONS | List every reservation and affected scope; required or high-risk unresolved matters still need an authorized disposition before that work proceeds. |
   | REVISE | Name the material corrections/questions; affected Build work waits for revision and matching recheck. |
   | REJECT | The proposal conflicts with the outcome, constraints or observed facts; return the decision to its owner. |

   An unavailable/not-selected critic has **no critic verdict**, not an inferred
   ACCEPT. Disagreement remains visible; the author cannot silently rewrite a
   critic's finding or treat a severity label as an automatic user waiver.
5. Default to a maximum of **two revision rounds**, or a stricter project limit,
   within the original authorized time/cost budget. A round comprises the gap
   check/critique, at most one author revision, and rechecking the changed claims
   against the exact resulting draft. All of that work draws from the same budget;
   a recheck is not permission for another uncounted revision or budget reset.
   A new draft invalidates an earlier draft's verdict until it is rechecked.
   Stop sooner on exhausted budget, unavailable required access/critic or a
   blocking decision. Extending the limit needs an applicable authorized decision,
   not an automatic third round.

After the bound, preserve every unresolved question, finding and disagreement in
**Open Questions**, including owner, impact, evidence needed and whether it blocks
specific work. Exhaustion never upgrades REVISE/REJECT or an absent required critic
to acceptance. Unaffected planning can continue within its actual scope; do not
erase a hard question merely to give the entire plan an accepted label.

## Decisions and synchronized acceptance changes

For high-risk specifications, give the authorized decision owner the exact draft,
critic verdict/reservations and remaining questions before the affected Build
work. If a prior user/project decision already covers that precise action and
scope, record its source and limits and continue within them; do not invent a new
approval step. If the decision exceeds existing authority or leaves a material
requirement unresolved, escalate that scope with the smallest concrete question.
Critic acceptance is not execution, publication, deployment or active-factory
adoption authority.

An accepted correction is first a proposed specification change. Preserve stable
acceptance IDs, task links, existing observations, failed history and explicit
waivers. For supported append-only scope, the existing
[acceptance planner](acceptance-planning.md) proposes synchronized bytes; the
[candidate helper](acceptance-candidates.md) may create an inactive reviewed
candidate with the original manifest. Neither registers new scope into the active
factory. The separately pinned [recovery review](recovery.md) can register named
changes in another snapshot; active adoption remains a separate authorized step.
Edits, deletion, reordering or unsupported custom shapes need a separately reviewed
manual synchronization of config, acceptance, brief, task/test mappings and gate
expectations. Do not edit only acceptance prose, reuse old observations as proof
of changed criteria, or reset all hashes. Record the reviewed proposal/adoption
state truthfully; a preview does not mean Build's accepted contract changed.

## Minimal task record and handoff

Record: request and scope/risk rationale; draft path/digest/version; inspected
repository subject and paths; participant selection/availability and observed
identity; authorized budget and round number; each finding's criterion, severity,
evidence, owner and disposition; critic verdict bound to its exact draft; proposed
revision and recheck outcome; Open Questions; applicable decision authority; and
acceptance-update state plus the next owner/action. Unknown fields stay unknown.
This is an adaptable human record, not a new runtime JSON schema or passing gate.

New factories receive the Plan route. Existing hashed Plan guides remain unchanged
until reviewed selective adoption. The compact migration continues to recognize
the exact frozen legacy detailed Plan and preserves complete project research;
it refuses an older/custom compact guide instead of overwriting it. Use the
installed reference while planning an authorized migration, never edit or re-hash
the living project's contracts merely to load newer guidance.

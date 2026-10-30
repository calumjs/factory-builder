# Evidence ownership, durability and revision identity

There are already sanctioned living records: `verification.md` holds gate
observations; `task-plan.json` holds task state and atomic evidence events. Both
are present in schema-2 manifests without content hashes. `release-handoff.md`
summarizes readiness/confirmation; it does not replace gate rows. Additional files
or an exempt evidence directory inside the factory are not supported by this schema.

## Who records what

- Build records the actual work revision, changed paths and checks actually run,
  and hands over targeted evidence. It updates its task progress using status.py
  within local-write authority; missing verification is not a done task.
- Verify maintains pre-merge rows in verification.md for the exact tested subject,
  and checks required gates. Release owns G3 and applicable post-action A/R/V1 rows
  for the actual deployed/installed/published subject and target. Required checks
  not run remain NOT RUN/BLOCKED; explicit optional choices remain WAIVED, including
  recorded failures. Record only observed results, never inferred success.
- The task owner records state/evidence atomically with status.py; a done task needs
  passing supplied evidence and completed dependencies. Learn reconciles the records
  and handoff with actual outcomes. Helpers validate claims; they execute no checks.

Put durable logs, screenshots, videos and reports in existing project evidence
storage **outside** `.software-factory`, e.g. a reviewed non-secret
`docs/factory-evidence/<subject-revision>/` tree or an already authorized artifact
store. Choose retention and access with the owner. Record stable artifact references,
content hashes where useful, check/environment, observation time and exit status.
Confirm artifacts remain accessible after a worker/session ends. Never place raw
secrets or sensitive records in logs; external storage/upload needs separate scope.
No evidence may be reconstructed as PASS merely because the temporary log is gone.

## Tested subject versus storage commit

Record two different identities: **subject revision** (the source/artifact actually
tested or deployed) and **evidence-storage revision** (the commit retaining those
records). Gate `Revision` and status event `revision` name the subject. Put the
storage revision in the handoff/review metadata after that commit exists; do not
make a commit contain its own unknown hash or replace the subject with the storage
hash. Use immutable full SHAs or equivalent artifact identities where available.

A narrow evidence-only follow-up can retain observations for subject S in storage
commit E without pretending S was E. Verify the E diff contains only the agreed
evidence paths and document that relationship for reviewers. A policy/skill/config,
test, dependency, source or runtime change is not automatically evidence-only and
may require new verification. The offline gate checker accepts an explicit subject
argument; it does not independently establish this relationship or CI trust.

If storage commit E triggers a new deployment, discover the actual deployed subject
and separately confirm that deployment. Old S observations cannot certify deployed
E by renaming their revision. Report confirmation pending/blocked or explicitly
waived until its evidence exists. Pre-action evidence and future G3/V1 remain
different stages. If CI is later integrated, choose a deliberate subject-selection
and evidence-storage policy rather than blindly comparing every row to HEAD and
creating a circular self-referential evidence requirement.

An authorized CI change may enforce integrity and stage gates using trusted scripts,
with secrets/data boundaries appropriate to the repository. No generic CI stub is
enabled here. An evidence commit, passing helper or waiver grants no merge/deploy/
upload authority. If integrity prevents recording, use the reviewed recovery
procedure; do not hand-edit passing observations to evade a failed check.

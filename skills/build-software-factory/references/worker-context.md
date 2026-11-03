# Selected worker planning context

`run.py plan` includes the selected task's acceptance wording from the indexed
`config.json` acceptance list. It includes that ID's current verification design,
environment, stage and requiredness, without copying result, revision, target,
timestamp or evidence fields into the worker context.

An optional project-added `test-map.json` can already map acceptance IDs directly
to design data, for example `{"A1":["tests/export_test.py"]}`. The planner selects
only the referenced entries and carries their values as uninterpreted JSON data.
It does not follow file references, inspect referenced files, infer commands or
interpret alternative nested map formats. Unknown formats, missing references,
duplicate task references and ambiguous verification rows produce context gaps.
Resolve those gaps before dependent work; absence supplies no requirement or waiver.
This is not a new factory contract or required test-map schema.

All supplied text stays in the prompt's untrusted JSON data block. Commands are
design data, not execution requests. The planner starts no workers or checks and
writes no factory or run record. Task context does not certify completeness, passing
evidence, project readiness, or authority. Confirm the task's test scope against the
actual change. Preserve explicit optional choices, and assess wider project gates
separately after integration rather than requiring every project gate for every task.

New context reads accept only regular, non-redirected files of at most 128 KiB and
check ordinary read stability. The rendered JSON payload is limited to 256 KiB,
with nesting and entry limits. These limits do not replace the existing whole-factory
integrity check or provide an adversarial atomic snapshot. Keep referenced designs
and handoff data non-secret and review worker prompts only within authorized storage.
No unrelated acceptance or verification row is copied into the selected context.

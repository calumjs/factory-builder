# Task status vocabulary

New configurations and rendered task plans use the existing status helper's exact
values: `blocked`, `pending`, `in_progress`, `done`. Values are case-sensitive;
`todo`, spelling variants and padded values are rejected, not silently translated.
The example's `blocked` default remains intentional until its prerequisites are
resolved. A configured status is supplied planning data, not proof of passing
checks; rendering never creates completion evidence or changes optional gates.

For an existing legacy record, preserve its bytes and history and review the actual
task state before choosing a canonical value. For a living `task-plan.json` status,
use the existing `status.py` preview and, after reviewing the event, `--apply` within
local-write authority. Retain the old status in the appended event. Do not mark
`done` merely to normalize vocabulary: it requires passing evidence for the named
revision and completed dependencies. If the legacy value is also in hashed
`config.json`, review the narrow contract correction and corresponding manifest
entry through [recovery](recovery.md); do not blindly re-hash or rescaffold. No
automatic legacy migration is provided.

`status.py --check` is a free-form observation label, not acceptance registration
or a typed gate identifier. To record a configured gate, use the existing
`incremental_records.py --kind gate` [preview/apply flow](incremental-workflow.md),
which validates the named row. Use that helper's `--kind task` for validated task
insertion; it does not add acceptance criteria.

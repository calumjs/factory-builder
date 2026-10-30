# Updating an existing factory

Never rescaffold over an existing factory, edit hashed files in place, or recompute every hash. `scripts/update_operations.py` is the one path: it changes reviewed operational configuration, the matching policy controls, relevant tool metadata, gate observations when needed, and their manifest entries — and starts no external action.

## Procedure

1. Confirm the factory path and local-write scope, then run `scaffold.py --check`. Hand-edited contracts or unregistered files go through [recovery.md](recovery.md) first; the updater refuses an invalid source and there is no force switch. Schema 1 needs its own reviewed migration. Pin the loaded builder first (generated launch-guide.md); a missing helper in an older install is a tooling blocker.
2. In approved scratch, write a partial operations patch, e.g. `{"done_videos":{"enabled":true,"scope":"Agreed narrated release demonstration"}}`. Omitted fields are preserved. No credentials.
3. Preview: `python scripts/update_operations.py --factory <root> --operations <patch.json>`. Flags for other reviewed opt-ins, each combinable with an empty `{}` patch:
   - `--delivery-gates` — adopt current G1/G2/G3 defaults and the Intake/Verify/Release addendum (a marked block that supersedes conflicting older instructions; custom content is retained — review the precedence).
   - `--assumptions <array.json>` — replace the structured assumptions ([operations-config.md](operations-config.md)).
   - `--recipe-runtime` — migrate a known pristine v1.2 dashboard so it can validate structured smoke recipes (adds `dashboard/recipes.py`, updates `operations.py`).
   - `--gate-runtime` — migrate known original v1.2–v1.5.1 dashboard `operations.py`/`recipes.py`/`gates.py` for structured checks and video triggers ([gates.md](gates.md)).
   - `--context-runtime` — migrate a known original v1.2/v1.3 dashboard for assumption context views.
   Each runtime flag applies only to known original bundled code; customized or unknown runtimes are preserved and refused for a separate manual review. Without the flag, a patch that needs the newer runtime is refused rather than silently narrowed.
4. Inspect the full diff and the `REVIEW PLAN` digest: config/policy consistency, retained custom rules and evidence, gate stages and rationale, video handoff, backup path, permission boundaries. Product or acceptance changes are outside this helper.
5. Within existing local-write authority, repeat with `--apply --approve-plan <digest>`. The digest binds the factory path and old/new hashes; any change to inputs or concurrent edits needs a fresh preview. Approval of one plan is not standing authority for others; an optional-test choice needs no extra approval.

## What the update preserves and resets

- Backups of changed originals and the manifest go to `<project>/.factory-update-backups/<plan-digest>/`, with `added-files.json` naming any added dependency; add that directory to the reviewed ignore policy. New destinations are created exclusively, so concurrent files are never overwritten.
- Research, acceptance, tasks, learning log and unrelated project files are untouched. Marked proposal blocks (intake design in policy.md, video recipe in release-handoff.md) are refreshed; a customized or ambiguous marked block is refused, not discarded. Old configs gain no hidden control fields.
- Smoke or video preference changes and a delivery migration reset active gate observations to NOT RUN, keeping row-level requiredness choices unless the patch changes smoke defaults; prior observations become quoted historical rows. Disabling videos retires V1 to history. Legacy eight-column rows migrate only when recognizable; ambiguous rows need manual review. Post-release-only checks stay post-action; a no-release exclusion is distinct from an unknown target.
- New contract files (CI template, scheduling, video recipe, boundaries.md, factory-run) are not copied into an existing factory automatically: read them from the installed builder, or review a selective addition with its manifest entry.

The manifest is written last with verified backups, but the update is not a multi-file atomic transaction. On interruption, stop, inspect the backups and any lock or temp file, restore the affected originals and manifest together (including `added-files.json` entries) or finish a newly reviewed plan; never delete a lock owned by an active writer. Run the integrity check and the stage-specific gate assessment afterwards.

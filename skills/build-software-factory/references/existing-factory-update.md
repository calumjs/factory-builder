# Narrow existing-factory and operations update

Do not rerun the scaffolder over an existing factory. Do not directly edit hashed config.operations, leave policy stale, or blindly recalculate every hash. The offline update helper changes only reviewed operational configuration, matching policy controls/default-gate guidance, relevant tool metadata, gate observations when needed and their manifest entries. It starts no external action.

## Preview and review

1. Confirm the exact factory path and authorized local write scope. Run the integrity check. Unreviewed contract edits must be resolved first; the updater refuses them. Schema 1 is unsupported and needs a separate reviewed migration.
2. In approved scratch, write an operations-change JSON object, such as `{"done_videos":{"enabled":true,"scope":"Agreed narrated release demonstration"}}`. This is a partial operations patch, not a complete product config. Existing omitted fields are preserved. No credentials belong here.
3. Preview with `python scripts/update_operations.py --factory <factory-root> --operations <changes.json>`. To opt an older factory into current delivery gates and Intake/Verify/Release guidance, add `--delivery-gates`. An empty `{}` operations patch is valid for that opt-in.
4. Inspect the full diff and `REVIEW PLAN` digest. Check config/policy consistency, retained custom rules and evidence, gate stage/rationale, video handoff, backup path and permission boundaries. Broader product/acceptance changes require a separately reviewed synchronized diff; this helper cannot rescope the project.
5. Within existing applicable local-write authorization and after reviewing that exact diff (an optional-test choice needs no extra approval), repeat with `--apply --approve-plan <digest>`. The plan is bound to the factory path and old/new file hashes; changed input or concurrent edits require a fresh preview and review. Approval of one plan is not standing authority for unrelated updates.

## Preservation and recovery

Original changed files and manifest are backed up under the project's `.factory-update-backups/<plan-digest>/`, outside the managed factory. Add these private backups to reviewed ignore policy before staging. Existing custom skill content is retained; an opt-in adds a marked delivery/intake addendum that supersedes conflicting old instructions. Review that precedence deliberately. Research, acceptance, tasks, learning and unrelated project files are preserved.

Smoke/video preference changes or a delivery migration reset active gate observations to NOT RUN, preserving deliberate row-level requiredness choices unless the patch explicitly changes smoke defaults. Retired V1 observations remain historical when videos are disabled. Prior observations are retained as quoted historical rows, not reused as passing current evidence. Extra required checks are retained. Legacy eight-column rows migrate only when their shape is recognizable; malformed or ambiguous rows require manual review. Post-release-only checks remain staged after the action; a no-release exclusion is distinct from an unknown target.

The helper writes the manifest last and keeps verified backups. Filesystem updates are not a multi-file atomic transaction: interruption can leave a blocked integrity state. Stop, inspect backups and any lock/temp file, restore the affected originals and manifest together or finish a newly reviewed plan. Never delete a lock owned by an active writer or bypass the failed integrity check. Run the contract check and stage-specific gate assessment afterwards. Valid hashes do not mean application checks ran or passed.

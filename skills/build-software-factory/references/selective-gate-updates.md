# Selective gate plan updates

Preview an operations patch with `update_operations.py --factory PATH --operations PATCH.json --selective-gates`. Review the row reason codes, exact diff and plan digest; the existing `--apply --approve-plan DIGEST` transaction remains required for local writes. This mode executes no checks and grants no execution authority.

The optional mode retains a configured row only when its recorded stage/design matches the old canonical plan and its typed plan, recipe, applicability and modeled dependencies are unchanged. Retention preserves the original row bytes, order, line ending, requiredness, subject, result and evidence. A retained FAILED row remains FAILED; a NOT RUN row and an optional waiver remain unchanged. Retention does not certify current evidence, rebind it to a new subject, or imply a new PASS. Ordinary evidence checks still decide whether it satisfies a requested subject and target.

Changed, missing, new or misaligned plans reset using the existing history mechanism. Prior observations, failures and customized plans remain historical, never current evidence. Retired video rows are archived and removed. Other unknown rows reset conservatively. Fixed `GATE RETAIN`, `GATE RESET` and `GATE FALLBACK` explanations expose gate IDs, reason codes and changed field paths, without including row values; the separately displayed reviewed diff still contains the actual local changes.

Dependencies are conservative:

- Any G3 reset, missing row or mismatched plan resets V1. Any G1 or G2 reset resets V2. Dependency closure happens after all reset seeds are classified.
- Changes to global post-merge target, applicability, rationale, accepted-by choice or the G3 recipe target reset all formerly or newly post-merge rows. A G3 command/environment-only change resets G3 and V1, preserving unrelated A/R plans.
- Per-row stage overrides include their rationale. Video preferences and designs reset or retire video rows without clearing unrelated observations.

The existing broad reset remains the default. Selective mode also falls back to it for whole delivery migration, legacy row schemas, unsupported line endings, changed exception or other controls, simultaneous assumptions updates, or actual copied runtime replacements. An explicit `smoke_gates.required` key always triggers broad fallback, even if its value is unchanged: this preserves the existing operation that reapplies G1/G2/G3 required defaults. Other editable required flags remain preserved. Ambiguous duplicate or malformed rows are refused for review.

No-op selective previews preserve the entire verification file. Mixed line endings and an unterminated retained final row stay intact; newly added rows go before that final row when necessary. Existing history remains deduplicated. Runtime receipt, backup, manifest-last ordering and approval digest behavior are unchanged; a mixed update receipt still describes runtime components only. Selective updates capture the research input for the existing concurrent-change check. Broader research/config changes require a separately reviewed plan; this mode does not infer dependencies for arbitrary custom controls.

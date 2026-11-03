# Gates: structured recipes, video triggers and risk-focused verification

There is one requiredness system: `smoke_gates.required` sets the G1/G2/G3 defaults, and an explicit Required=no/false on a living row is the operator's waiver. Legacy `not_run_is_blocking` is not a second setting; in a reviewed migration keep required NOT RUN blocking or express the operator's optional choice, preserve the original and its context during review; never silently discard the field or convert it to PASSED. Configuring any of the metadata below establishes no tool permission, CI execution, env allowlist or application truth.

## Select the factory directory

Pass the directory containing the factory's `manifest.json`: from a repository root this is normally `--factory .software-factory`, or `scaffold.py --check .software-factory` for integrity checking. `--factory .` is valid when the current directory is the factory itself. Missing-manifest diagnostics name the supplied absolute root and expected manifest, and suggest a child `.software-factory` only when a regular manifest can be observed without traversing a symlink or junction. A hint does not validate or automatically select that child. Redirected paths remain rejected; use the intended non-redirected location rather than bypassing the check.

## Structured smoke recipes (`smoke_gates.checks`)

Optional per-gate records mapping G1/G2/G3 to an exact design. A synthetic example — not a claim these commands exist:

```json
{"smoke_gates":{"checks":{
  "G1":{"command":["python","tests/smoke_cli.py"],"environment":"isolated installed-package fixture","env_names":[],"target":{"kind":"artifact","value":"synthetic-package-v1","base_url_env":null}},
  "G3":{"command":["python","tests/smoke_web.py"],"environment":"authorized released service","env_names":["BASE_URL"],"target":{"kind":"web","value":"https://fixture.example.invalid","base_url_env":"BASE_URL"}}}}}
```

- `command`: 1–64 non-empty argv strings, each ≤ 2000 characters, no control characters. Data only; the builder never runs it.
- `environment`: a non-empty printable label with no outer whitespace, line separators or Markdown pipes. Target values use the same form.
- `env_names`: ≤ 64 unique variable names, no values or assignments. The checker never reads or verifies them.
- `target`: exactly `kind` (`web`/`artifact`), `value`, `base_url_env`. Web values are base HTTP(S) URLs without userinfo, query or fragment, with `base_url_env` null or a declared `env_names` member. Artifact targets use null `base_url_env` and a meaningful package or installed identity. A structured G3 target fills an unconfirmed legacy `target_kind`/`deployed_url`; an explicit conflicting legacy value is rejected, and a G3 command conflicts with an accepted no-release exclusion.

The generated row shows the canonical argv, env names and environment label and starts NOT RUN with a blank actual target. A still-required PASSED row must match the configured design, environment and target as well as subject, time, exit status and evidence. Changing a recipe through the synchronized updater resets active observations and keeps failures, waivers and history. Free-text `pre_merge`/`targeted`/`post_merge` remain designs until commands are inspected.

## Video triggers (`done_videos.triggers`)

A unique array of `pre_merge_preview`, `post_g3_release` or both; enabled videos need at least one. Omitted keeps the legacy release-only V1; disabled creates no V rows.

- `pre_merge_preview` → expected V2 at pre-merge for its local/preview subject. Preview-only can coexist with accepted no-release scope.
- `post_g3_release` → reserved V1 at post-merge for the shipped subject after a still-required G3 (a waived G3 or V1 is disclosed). A release trigger cannot coexist with no-release scope.

V2 never certifies V1. Missing, moved or duplicate expected rows are errors; each present row's optional choice is respected. Do not read triggers from natural-language scope. Manually added V2 rows stay extra checks unless the operator selects the structured trigger; removing a structured preview trigger retires its active row to quoted history and preserves manual extras. Preference changes reset observations, keep waivers, and create no footage or PASS.

## Existing factories

Use `update_operations.py`'s preview/digest/apply flow. New checks or triggers need compatible copied dashboard, recipes and gates helpers: `--gate-runtime` upgrades known original v1.2-v1.5.1 sources, the exact published v1.7 gate helper, and a known missing v1.2 recipes dependency; custom or unknown code is refused and preserved. The published v1.7 gate helper remains in place by default and needs the opt-in to receive duplicate-policy diagnostics. Review code, config, policy, rows, manifest and the backup together. A plugin upgrade alone rewrites nothing.

## Risk-focused verification

A green happy-path suite is evidence for the paths it exercised. When intake promises idempotency, durable state, recovery or untrusted identifiers, Plan assigns a risk-focused design and, where risk and budget warrant, an independent implementation review. For an unrelated project choose its own relevant risks.

- **Caller identifiers and retries:** define the documented identifier alphabet and the replay, conflict and removal behaviour, then test boundary and collision values through the public interface, the persistence round-trip and a fresh-process restart (in JavaScript dictionaries that includes `__proto__`, `constructor` and `hasOwnProperty` — inherited properties, own-key checks, serialization and reload — resolved with a `Map` or null-prototype design; other stacks have their own equivalents). Never fix a defect by silently narrowing accepted IDs. Resolve ambiguous retention or deletion semantics with the owner.
- **Durable persistence:** read the storage API contract for the actual platform and version, then exercise partial, short, zero-progress and failed writes at pre-commit boundaries in a disposable fixture, with multibyte data for byte-based contracts, and verify the previous committed state survives and the restart path is honest. A kill-before-rename test and an fsync/rename pattern each cover a different failure mode and neither proves every byte was written or universal power-loss durability; Node's `fs.writeSync` returns a byte count, so prove complete progress or abort before replacing committed state. Never inject faults into production data or weaken platform protections for a test.
- **Secrets and connection strings:** use the generated connection-string-review.md (bundled [review guide](../assets/templates/connection-string-review.md)). R1 is selected research, not a hardcoded rule. Separate detection from reviewed synthetic-fixture classification; hostnames, usernames and documentation paths are not exemptions; test mixed and unknown-provenance cases with invented values; a criterion change needs review and fresh exact-subject observations.
- **Repair and re-gating:** keep the reproducer and exact failing subject; record discovered required failures as FAILED or BLOCKED even after an earlier green suite (WAIVED with the failure for optional rows); repair on a new subject, review the final diff and rerun the targeted, acceptance and production-equivalent checks for that subject. Mixed old/new subject rows cannot certify the repaired revision.

Reference contracts consulted when these examples were written (read 2026-10-30): [Node 24 `fs.writeSync`](https://nodejs.org/docs/latest-v24.x/api/fs.html#fswritesyncfd-buffer-offset-length-position), [`Object.create` and null prototypes](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/create). Check the installed version in a real task.

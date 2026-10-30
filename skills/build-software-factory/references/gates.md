# Gates: structured recipes, video triggers and risk-focused verification

There is one requiredness system: `smoke_gates.required` sets the G1/G2/G3 defaults, and an explicit Required=no/false on a living row is the operator's waiver. Legacy `not_run_is_blocking` is not a second setting; in a reviewed migration keep required NOT RUN blocking or express the operator's optional choice, never drop or convert the key. Configuring any of the metadata below establishes no tool permission, CI execution, env allowlist or application truth.

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

Use `update_operations.py`'s preview/digest/apply flow. New checks or triggers need compatible copied dashboard, recipes and gates helpers: `--gate-runtime` upgrades only known original v1.2–v1.5.1 sources (and a known missing v1.2 recipes dependency); custom or unknown code is refused and preserved. Review code, config, policy, rows, manifest and the verified backup together. Factories updated without these fields keep their older compatible helpers unless a runtime migration is selected; a plugin upgrade alone rewrites nothing.

## Risk-focused verification

A green happy-path suite is evidence for the paths it exercised. When intake promises idempotency, durable state, recovery or untrusted identifiers, Plan assigns a risk-focused design and, where risk and budget warrant, an independent implementation review. For an unrelated project choose its own relevant risks; these examples are proposals, not new mandatory gates.

**Caller identifiers and retries.** Define the documented identifier alphabet and the replay, conflict and removal behaviour. Test boundary values through the public interface, persistence round-trip and a fresh-process restart. In JavaScript dictionaries, cover `__proto__`, `constructor` and `hasOwnProperty` when the alphabet allows them — inherited properties, own-key checks, lookup/insert, serialization and reload — and choose a `Map` or null-prototype design proven across the round-trip; other stacks need their equivalent collision, normalization and encoding cases. Never fix a defect by silently narrowing accepted IDs. Test repeats after restart and after removal against the accepted contract (replay identity, conflicts, tombstone/retention, side effects), resolving ambiguity with the owner; distinguish fresh-process retries from repeated calls on one in-memory instance.

**Durable persistence and fault injection.** Read the storage API contract for the actual platform and version. In a disposable fixture exercise partial and repeated short writes, zero progress and write failures at pre-commit boundaries, with multibyte data for byte-based contracts. Preserve the previous committed state on incomplete preparation; verify readable state after restart, honest error reporting and cleanup/retry. A kill-before-rename test is a different failure mode and does not prove write completion; fsync and rename do not prove every byte was written, and a generic rename pattern does not establish universal power-loss durability. For Node `fs.writeSync`, the return value is a byte count: inspect the overload, buffer/offset/encoding handling and error path, and prove complete progress or abort before replacing committed state. Never inject faults into production data or alter platform protections for a test.

**Secrets and connection strings.** Use the generated connection-string-review.md (or the bundled [review guide](../assets/templates/connection-string-review.md)). R1 is selected research, not a hardcoded rule. Separate detection from reviewed synthetic-fixture classification; hostnames, usernames and documentation paths never establish an exemption. Test mixed and unknown-provenance cases with invented values, keep real suspected values out of logs and evidence, and treat a criterion change as needing review and fresh exact-subject observations.

**Repair and truthful re-gating.** Keep the reproducer, exact failing subject, expected/actual result and durable evidence. Record discovered required failures as FAILED or BLOCKED even after an earlier green suite (WAIVED with the failure retained for optional rows). Repair on a new subject, review the final diff, and rerun the targeted, acceptance and production-equivalent checks for that subject before restoring readiness. Mixed old/new subject rows cannot certify the repaired revision.

Primary references read 2026-10-30 (check the installed version in a real task): [Node 24 `fs.writeSync`](https://nodejs.org/docs/latest-v24.x/api/fs.html#fswritesyncfd-buffer-offset-length-position), [`Object.create` and null prototypes](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/create). The builder runs no Node code and injects no application faults.

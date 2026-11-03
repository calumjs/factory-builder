# Private supplied analytics, Learn proposals and experiment records

`factory_analytics.py` is an optional **installed helper**, separate from copied factory runtimes. It reads explicitly supplied sanitized local JSON, analyzes a declared task cohort, renders an optional dashboard panel, and writes an uncommitted Learn proposal. It neither collects sessions nor executes experiments. Existing factories, gates, waivers and learning history remain unchanged; no runtime migration is needed for this helper. It requires the installed `run_traces.py` and dashboard supplemental renderer introduced with the supplied-trace feature.

All records and outputs are private by default. Model names, source labels, counts, costs, subjects, task names and proposed changes may be sensitive. Review before sharing or committing. Inputs must be explicitly authorized sanitized exports; this command grants no permission to read private harness stores. No hooks, raw-log adapters, credentials, providers, network calls, pricing lookup, live PR query, allocation execution or automatic adoption are included. Broader event collection and runtime-discovered populations remain deferred.

## Bounded end-to-end example

Run from the installed skill directory; replace `FACTORY` and `PRIVATE_OUTPUT` with explicit local paths outside the factory. Inputs are synthetic examples, not instructions to export actual session logs.

```text
python scripts/factory_analytics.py --factory FACTORY --experiment assets/example-analytics-experiment.json --definition-only --output PRIVATE_OUTPUT/definition.json
```

Review the definition and retain its `canonical_experiment_digest`. For the unchanged example it is `2c121f1f455417c9977387606ddc05f2d1351982c99544641a3a22ac6e5f0f29`. The definition export withholds `assignment_evidence_ref`; it is a readable view, **not** a replacement input for the original digest-pinned experiment.

```text
python scripts/factory_analytics.py --factory FACTORY --experiment assets/example-analytics-experiment.json --experiment-pin 2c121f1f455417c9977387606ddc05f2d1351982c99544641a3a22ac6e5f0f29 --trace assets/example-analytics-traces.json --assignments assets/example-analytics-assignments.json --as-of 2026-12-15T00:00:00Z --output PRIVATE_OUTPUT/analysis.json
```

Repeat with a new output and `--format html` for the factory dashboard plus optional analytics panel, or `--format learn` for a seven-column Learn draft. JSON contains only analytics and an optional supplied decision; it does not embed the factory snapshot. The HTML factory overview is a separate read-only snapshot outside the analytics digest. Changing factory mtimes cannot change that digest.

The synthetic records demonstrate exported observations after the event window and analysis over a month later: both remain eligible. In the primary declared cell, A has 2/2 units with mean build minutes 2.5; B has 2/2 with mean 4.5. These are conditional descriptive values, not an adoption recommendation. The example costs are supplied values; no pricing is inferred.

No output rewrites `learning-log.md`. Inspect the draft, record an explicit decision, and use the project's existing review process for any adoption. Use new filenames and experiment versions to preserve prior records. Existing output needs explicit `--replace`; all input aliases, inside-factory outputs and outputs above 2 MB are refused. Inputs are distinct regular files, at most 1 MB each, parsed with duplicate-key/nonfinite-number rejection through the existing supplied-trace reader. Error messages withhold private paths and values.

## Strict version 1 experiment

The executable examples are the complete schema fixtures. Extra or missing keys are rejected throughout. Boolean values cannot substitute for integer versions/counts. Text is bounded, printable, single-line and trimmed. Version fields are positive integers. All timestamps require an explicit timezone.

Top-level fields:

| Field | Meaning |
|---|---|
| `schema_version` | Exactly integer 1 |
| `experiment_id`, `version` | Private experiment identity and definition version |
| `created_at`, `timing` | Supplied creation time; `prospective_claim` or `retrospective` |
| `method` | `observational`, `operator_allocated`, `before_after`, or `randomized_claim` |
| `population` | Explicit requested task population, not inferred from available traces |
| `assignment_unit` | Exactly `task` in this first slice |
| `assignment_description`, `assignment_evidence_ref` | Supplied allocation explanation and private reference; reference is withheld and never dereferenced |
| `variants` | Exactly two definitions with `id`, positive `version`, `intervention`, `start`, `end` |
| `analysis_attempt` | Exactly `predeclared_first`; an explicit supported estimand choice, not a universal retry policy |
| `min_units`, `minimum_rationale` | Operator-chosen threshold of 2–100 per variant plus rationale; not a power analysis |
| `stopping_rule`, `confounders` | Supplied review rule and anticipated limitations; neither is enforced as an operational stop |
| `allocations` | 2–100 prelisted task allocations, both variants represented |
| `metrics` | 1–12 fixed metric definitions, exactly one primary |
| `learn` | Printable `hypothesis`, `proposed_change`, `owner` for an uncommitted proposal |

Windows are `[start, end)`, applied to supplied attempt `started_at`. Parallel methods require matching windows; `before_after` requires ordered nonoverlapping windows in variant order. Prospective claims require `created_at <= start`; all analyses require `created_at <= as_of`. These are consistency checks on supplied claims, not trusted clocks or verified preregistration. A prospectively enumerated observational population is permitted: listing observed variants does not establish that the operator assigned them. Randomization is never performed or verified. Retrospective analysis is labeled post hoc; before/after retains time confounding. Analysis before a window closes is visibly marked `observation_window_open`.

Each allocation is exactly `{unit_id, task_id, variant, first_attempt_id}`. Unit, task and pinned first-attempt IDs are unique. The stable task allocation cannot change with subject, result or retry. Independent tasks may legitimately use the same code subject: shared subjects trigger a qualified dependence warning, never automatic duplicate exclusion. Exact duplicate run/attempt mappings are refused.

## Metrics and declared comparison cells

Each metric has exactly `id`, positive `version`, `description`, `selector`, `phase`, `unit`, `role`, `cell`, `threshold`. IDs and selector/phase/cell definitions must be unique. Role is `primary`, `secondary`, or `guardrail`; exactly one is primary. Primary and guardrail comparison cells are fixed in the pinned definition; available values in other status/source cells are secondary descriptive only and cannot replace them.

| Selector | Unit | Phase |
|---|---|---|
| `sessions`, `human_turns` | `count` | One explicit phase |
| `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens` | `tokens` | One explicit phase |
| `active_minutes` | `minutes` | One explicit phase |
| `cost` | `currency` | One explicit phase |
| `rounds` | `count` | `null` |
| `files_changed`, `lines_added`, `lines_removed`, `commits_after_handoff`, `human_review_comments`, `failed_checks` | `count` | `null` |

Phase is one of the existing trace phases: intake, plan, build, verify, release, learn, run, review. For phase measures, sum **all supplied model rows for that selected phase**. No matching phase means unavailable, never zero. Any unavailable row or mixed status excludes the unit for that measure. This does not prove every model/session was supplied: `complete=true` is only a supplied run-level claim. Active minutes are a sum of supplied phase/model active minutes, not elapsed time; overlapping work can be counted in both rows.

`cell` is exactly `{status, source_label, currency}`. Status is `measured`, `supplied`, or `estimated`—each remains an unverified status claim. Source label must match exactly; matching labels are not proof of comparable instrumentation. Currency is a three-letter uppercase code for cost and `null` otherwise. Cost requires every selected row to have that same currency. No currency conversion, cost inference or repricing occurs. Cost aggregation exists only in this analytics helper; `run_traces.py` still does not aggregate cost. Different currencies and mixed statuses are excluded, not pooled. Different model labels between included token cohorts add a definition-comparability limitation.

`threshold` is `null` except for a guardrail, where it is `{direction: max_mean|min_mean, value: bounded_nonnegative_number}`. Each variant is evaluated only in the guardrail's declared cell. Below-minimum or missing observations retain `guardrail_unavailable_or_insufficient` in the limitations. Any nonempty observed mean beyond the bound also produces `guardrail_threshold_exceeded_observed`; that comparison does not clear the insufficient-sample limitation. A passing variant never masks the other's breach or missingness. These describe observed conditional means, not safety approval or automatic stopping.

Every metric is independently eligible: missing output tokens do not invalidate supplied active minutes or outcomes. All numbers inherit trace type/finite/nonnegative bounds. Per-unit and cohort sums are bounded by 10^12; float sums use `math.fsum`. Empty cohorts report null mean/min/max, not zero. Nonempty cohorts report n, mean and observed min/max, with no dispersion, significance calculation or causal interpretation.

## Strict version 1 assignment inventory

Top level is exactly `{schema_version: 1, experiment_digest, units}`. `experiment_digest` must equal the canonical experiment digest. Every supplied unit is exactly `{unit_id, inventory_complete, attempts}`; units must be known and unique. Missing inventories remain in the requested denominator. A maximum of 500 attempts can be listed, while the existing trace input limit is 100 runs including retries and unassigned records.

Each attempt is exactly:

```json
{"attempt_id":"attempt-0","ordinal":1,"run_id":"run-0","subject":"source-subject","storage_subject":null,"deployed_subject":null,"started_at":"2026-11-01T08:00:00Z","state":"observed","error_reason":null}
```

`state` is `observed` or `error`. Observed attempts require one existing unique trace run ID, an exact match to its source subject, and `error_reason:null`. Error entries require `run_id:null` and a bounded printable reason; no measure is fabricated. Storage/deployed subjects are optional separate claims and never substitute for the source subject. Error reason/reference contents are not exported.

Attempt IDs are globally unique, and an allocation's pinned first ID cannot appear under a different task. Ordinals must be contiguous starting at 1, with nondecreasing supplied start times. If the pinned first ID is present it must have ordinal 1. The actual binding from first ID to trace remains supplied and can be dishonest; checks detect contradictions, not truth. The first ID is never selected from timestamp order, latest pass or lowest value. Missing first attempts are excluded without retry fallback. Claimed-complete inventories do not attest that omitted attempts never existed.

Require `started_at <= observed_at <= as_of` for observed attempts, and `started_at <= as_of` for error entries. Observation age is displayed as context and is never an eligibility filter. Historical experiments do not expire after 30 days. `summarize()` is reused for trace validation/normalization only; its output-token averages, freshness labels and exclusions are not analytics eligibility.

## Denominators, missingness and limits

Each metric reports both variants, allocated/included/excluded counts, units with later listed attempts, excluded later-attempt count, and a full disposition table. First-attempt categories partition allocated units: no inventory, incomplete inventory, missing first attempt, error, out of window, open/censored, closed, unavailable PR state, merged/incomplete, merged/complete. Metric categories then partition the merged/complete subset: unavailable measure, mixed status, incompatible currency, outside declared cell, included. Earlier exclusions take precedence, so these are not independent prevalence estimates of all possible flaws. No missingness is a success or zero.

The estimand is the mean among units whose predeclared first attempt was supplied as merged and complete and whose selected measure matches its declared cell. Closed and abandoned work is excluded; open work is censored. These conditional summaries can favor a variant with more failed, delayed or incomplete tasks. Retry cost is omitted even though retry counts are visible. Primary metrics and guardrails can describe different subsets. Unequal included/allocated fractions add `differential_inclusion` without a threshold; an open first attempt after window end adds `censored_open_attempts`. Unassigned traces are counted and excluded, not silently added to the population. A shared subject among assigned/unassigned runs is only a possible dependence signal.

All outputs retain descriptive/supplied/selection/coverage limitations. Below-minimum cohorts remain insufficient; the operator's minimum is not evidence of statistical adequacy. No automatic selection, policy change, comparison winner, p-value or causal effect is reported. Richer retry-cost/failure-inclusive estimands, statistical designs and repeated-peeking/version-history analysis are deferred.

## Pins, decisions and Learn

Digests are SHA-256 of canonical parsed JSON: UTF-8 `json.dumps(sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)`. Object-key order, BOM and formatting differences disappear; array order remains significant. This is **not a raw-byte hash**. The analysis digest binds only the analytics object: all three canonical input digests, explicit as-of, definition/selector interpretation, population and derived counts/values/limitations. Optional decision and the HTML factory overview are outside it. A digest proves neither truth, permission, prospective allocation nor attribution.

An optional separate decision is exactly:

```json
{"schema_version":1,"analysis_digest":"64 lowercase hex characters","decided_at":"2026-12-15T00:01:00Z","decision":"inconclusive","owner":"operator","rationale":"Review additional evidence"}
```

Decision is `keep`, `revise`, `reject`, or `inconclusive`; its supplied time must be no earlier than the analysis as-of. The time is not independently verified. The tool labels it operator supplied and performs no adoption. A `keep` record cannot remove insufficient evidence or guardrail limitations. Use a new output to retain each prior analysis/decision.

Learn output uses opaque `primary-cell`/variant indices and digests in the evidence column rather than private source/model/subject labels. Hypothesis, proposal and owner are still supplied private text; review them before committing. The writer escapes HTML, pipes and backslashes, refuses multiline cells and validates the exact seven-column Learn format. Approval/outcome remains pending or supplied, with limitations and no adoption. No factory record is appended or rewritten automatically.

# Explicit private run traces

The installed `scripts/run_traces.py` validates an explicitly supplied, sanitized
trace file and adds its claims to the existing read-only overview. It never reads
Claude/Codex session stores, searches working directories, queries PR services,
installs hooks or modifies factory records. This is a local portion of a trace
workflow, not automatic instrumentation or an authenticated cost/outcome history.

```text
python <trusted-builder>/scripts/run_traces.py --factory <factory-root> --trace <approved-private-traces.json> --output <private-overview.html> --as-of 2026-11-03T08:01:00+00:00
python <trusted-builder>/scripts/run_traces.py --factory <factory-root> --trace <approved-private-traces.json> --output <private-overview.json> --format json --stale-after-minutes 1440
```

The date is a synthetic example; choose the actual assessment time or omit it to
use current UTC. Output must be outside the factory and cannot replace the input.
Existing output requires explicit `--replace`. Validation failure leaves old
output unchanged. The JSON is the ordinary dashboard DTO plus the opt-in
`supplied_run_traces` object. Normal dashboard invocations remain unchanged.

## Private inputs and provenance

Use [the synthetic example](../assets/example-run-traces.json) as the exact
version-1 shape. All keys are required and unknown fields are refused. Input is
limited to one local regular file of 1,000,000 bytes, 100 runs and 64 phase/model
rows per run. Duplicate JSON keys, non-finite numbers, redirected paths,
unsupported versions and changing input metadata are rejected. These bounded
checks are not an atomic filesystem snapshot or an I/O timeout; use stable
approved local files. No references in the file are opened or fetched.

Each run has an explicit `run_id`, exact supplied `subject`, aware `observed_at`,
`source_label`, private `evidence_ref`, supplied `complete`, `pr_state`, `risk`,
`rounds`, `verdict`, `phases` and `outcome`. A run ID can appear once per snapshot
and binds one subject; even a duplicate with a different subject is refused.
Provide distinct run IDs for distinct runs, and establish attribution before
preparing the input. Working directory, author date, similar model names or an
apparently matching commit do not establish attribution or missed fixes.

PR state is `open`, `merged`, `closed` or `unavailable`; it is supplied, not queried.
Risk is `low`, `medium`, `high` or `unavailable`; verdict is `approve`,
`request_changes`, `blocked`, `waived` or `unavailable`. These claims have no gate
effect. They are not formal GitHub approval, release readiness or live state.

`source_label` describes the supplied source; `evidence_ref` identifies the
private provenance retained by the operator. The helper validates but withholds
that reference from both exports. Every other documented field may appear in
the private output. Model names, numbers, run IDs, subjects and source labels can
still disclose sensitive activity: none is automatically safe to commit. Keep
inputs/outputs in approved private storage, and review all exported fields before
sharing. HTML escaping prevents markup execution; it does not redact secrets.

## Typed measurements and outcomes

Every metric has exactly `status` and `value`. Status is `measured`, `supplied`,
`estimated` or `unavailable`. The first three require a finite nonnegative number
at most 1,000,000,000,000; unavailable requires null, never a fabricated zero.
Measured means the input claims measurement, not that this helper verified it.
Supplied distinguishes a provided number without an asserted measurement method;
estimated retains an explicitly declared estimate. Only active minutes and costs
may be fractional; rounds, sessions, turns, tokens and outcome counts are integers.

Phase is one of intake, plan, build, verify, release, learn, run or review. Each
phase/model pair is unique within a run. It has sessions, active_minutes,
human_turns, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens
and cost. Cost adds a three-uppercase-letter currency when available, or null
when unavailable. There is no price table, token-to-cost conversion, currency
conversion or cost sum/average. Preserve the source's counting definitions;
provider token/cache definitions and session boundaries need separate review
before comparing activity across tools. No raw harness-format adapters are supplied.

Outcome metrics are files_changed, lines_added, lines_removed,
commits_after_handoff, human_review_comments and failed_checks. Their counting
scope must come from the explicitly prepared source. Commit counts do not mean
the factory missed fixes, and comments/checks do not establish quality or cause.
No Git history, author identity, bot classification, PR state or timestamps are
inferred. Unknown values stay unavailable, including for an open PR.

## Display and aggregation boundaries

The run table shows the supplied risk, rounds and verdict alongside PR state,
completeness, observation age and exclusions. An open PR appears in progress.
The output-token stack shows supplied phase/model values, with exact values and
statuses in an adjacent table. If any phase output is unavailable or no phases
are supplied, the whole stack total is unavailable rather than a misleading
partial total. A complete available set of zero values may truthfully total zero.
For incomplete traces, any displayed values describe only the supplied phases.

Only runs **supplied as merged and complete**, observed within the freshness
window, with every phase output value available and all such values having one
declared status enter an output-token average. Measured, supplied and estimated
cohorts are separate. Each mean reports its included and excluded counts across
the entire supplied snapshot; other status cohorts count as exclusions for that
mean. Empty cohorts report unavailable, not zero. Per-run reasons and overlapping
reason counts explain open/closed/unknown PRs, incomplete or stale records,
unavailable phase values and mixed statuses. Individual run totals are bounded
to 1,000,000,000,000. This is arithmetic over supplied claims, not verified
completeness, deduplication across snapshots, population statistics or model
recommendations. Fresh means recent, never trustworthy. Future timestamps fail.

## Compatibility and deferred work

Run the trusted installed helper; it uses the installed dashboard renderer and
has no copied runtime dependency. Existing factories and their copied helpers,
static index, manifest, policies and evidence remain untouched. New generated
dashboard code retains the same ordinary behavior; the internal supplement hook
accepts only trusted renderer output, never a raw HTML field from trace JSON.
Any separate copied-runtime update still uses the existing reviewed migration.

Automatic session-end hooks, private log parsers, live PR adapters, cost pricing,
independent provenance verification, outcome causality and automatic model routing
remain out of scope. Adding any requires its own explicit data/authority boundary
and source-format verification. This helper neither runs them nor grants authority.

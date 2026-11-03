# Record an explicit batch of gate observations

Use the trusted installed `scripts/incremental_records.py` with `--kind gate-batch`
to preview observations already obtained for one exact subject. This reuses the
single-gate writer, whole-factory snapshot/digest and atomic replacement of the one
living `verification.md` file. It executes no tests or commands, reads no CI report
or evidence URL, and independently verifies no observation.

The input is a nonempty JSON array of at most 64 existing gate-observation objects:

```json
[
  {"gate":"G1","result":"FAILED","revision":"exact-observed-subject",
   "environment":"isolated test environment","evidence":"private-evidence-reference",
   "target":"actual-tested-artifact","checked_at":"2026-11-01T12:00:00Z","exit_status":"1"},
  {"gate":"A1","result":"BLOCKED","revision":"exact-observed-subject",
   "environment":"isolated test environment","evidence":"recorded blocker reference",
   "target":"","checked_at":"","exit_status":""}
]
```

These are schema examples, not real observations. Supply every shown field, with
no extra keys. Every item must name a distinct existing configured gate and the same
nonempty, unpadded exact subject; unresolved placeholders such as `unknown` or `TBD`
are rejected. Mixed subjects, duplicate/unknown gates, duplicate
JSON keys, nonfinite values and any invalid item reject the entire batch. The regular
input file and serialized batch are limited to 256 KiB; each field to 8192 characters.
No field is truncated. References containing pipes must use a non-secret evidence
file reference instead of embedding the pipe-bearing content in the table.

```sh
python <trusted-builder>/scripts/incremental_records.py --factory <factory> --kind gate-batch --input <private-observations.json>
python <trusted-builder>/scripts/incremental_records.py --factory <factory> --kind gate-batch --input <private-observations.json> --apply --approve-plan <exact-preview-digest>
```

Review the complete private diff and digest before applying. A changed input or
factory requires a fresh preview. Validation failures produce no partial update;
the existing apply path checks the captured factory and replaces the completed
record once. Failed replacement preserves the original record. This is the same
local-file safety model as the single writer, not a distributed lock or transaction
over external evidence sources.

Gates are applied in canonical ID order only to make bytes and digests deterministic.
That order says nothing about when checks executed: every supplied timestamp is kept.
**G3 and V1 cannot share a batch in either order.** Record G3 in a separate reviewed
step before a V1 observation that depends on it. A still-required G3 must already
have matching passing subject/target evidence, and V1's actual observation time must
not precede it under the existing gate rules. Existing optional G3 choices remain waivers; this restriction adds no
requirement to run a waived check.

PASSED claims use the existing gate validation, including concrete evidence and
actual targets; no default target or passing result is supplied. Existing optional
requiredness is preserved, and even an optional PASSED observation must be concrete.
Changed prior rows remain quoted history, including failures. Excluded rows are left
unchanged, not carried forward to the new subject. A batch neither broadens task
scope nor makes A/R gates optional; project-wide readiness still depends on its
configured requirements. Use the separate scoped-assessment workflow when reviewing
an explicitly bounded change, without presenting that result as project readiness.

# Optional G3-to-acceptance trace

The installed builder's `scripts/acceptance_links.py` reads an explicitly selected,
non-secret JSON record outside the factory. It does not change any factory, gate,
acceptance result, readiness decision, CI policy or waiver. No sidecar is generated
or required; existing factories and their gate checks work unchanged.

Example trace-only record in approved private scratch:

```json
{"schema_version":1,"gate":"G3","subject":"exact-subject","target":"actual-artifact",
 "links":[{"acceptance_id":"A1","result":"NOT RUN","evidence":"","observed_at":""}]}
```

Run `python <builder>/scripts/acceptance_links.py --factory <factory> --record
<outside-json> --subject <actual-subject> --target <actual-target>`. Select the
subject and actual target independently; a configured target does not prove a
release. Each unique link names an existing configured A ID and records PASSED,
FAILED, BLOCKED or NOT RUN. A PASSED claim requires an evidence reference and an
ISO observation time with timezone. Other results may have empty evidence/time.
Links inherit the envelope's subject/target **as supplied claims**: the helper does
not verify that a reference belongs to either or that a check actually ran. Keep
private details out of the record and logs. For historical attempts, retain separate
records in authorized external evidence storage; this helper enforces no append-only
storage or access policy.

The output separately shows each canonical A row's stage, requiredness, recorded
result and revision, and the G3-linked claim. A linked PASSED claim cannot mark an
A row passed. An applicable, required G3 with matching PASSED evidence and the
existing G3 checks may be shown as a **recorded positive claim, not attested**.
FAILED, NOT RUN, WAIVED or NOT APPLICABLE G3 is never a positive claim. Waived rows
remain WAIVED with the underlying recorded result; no additional approval is needed
to make an optional-gate choice. A valid NOT RUN link with no evidence is shown as
UNCONFIRMED. There is no age-based TTL or inferred completeness for unlisted IDs.

The result always says `TRACE ONLY — NOT READINESS OR PROOF`. Exit 0 means only that
the record was structurally valid and bound to the supplied subject/target, including
when its claims failed or were waived. Exit 1 means the record or G3 binding differs
from those explicit inputs; exit 2 means malformed/unsafe input or unavailable factory.
None means application checks ran. The helper checks ordinary read stability, bounded
regular files and existing factory integrity, not an adversarial atomic snapshot.
Do not make this trace a CI gate or change required checks without a separate design
and authorization. Use `gates.py` for existing stage readiness semantics.

# Task-fitted connection-string checks

Use only when this project's risks/acceptance/research call for secret checks.
R1 is a positional selected-research check, not a built-in connection-string rule.
Inspect its actual definition before changing anything. A literal scheme search
finds candidates; it does not classify secrets or establish complete coverage.
Use the project's existing approved scanner and fitted review procedure. The
builder supplies guidance, not a secret scanner or automatic exception mechanism.

## Review every candidate in permitted non-secret context

Do not print, copy into evidence, upload or attempt to use a suspected credential.
Record a redacted file/line reference, category, reviewer rationale, check version,
exact tested subject and durable non-secret evidence. Where authority does not
permit inspection, keep the result BLOCKED/unknown and request the owner decision.
Review existing approved fixture/service definitions without opening secret files.

Classify an explicitly synthetic fixture only after establishing its actual scope:
the value is deliberately generated/disposable for the isolated test service, has
no reused real identity/password, cannot access production/staging or another
real service, and its service/network/lifecycle configuration supports that claim.
Names like ci/postgres, localhost, *.localtest.me, or a documentation path alone
prove none of this. Even a loopback address may reach a real service or tunnel.
A label saying SYNTHETIC is a claim to verify, not an exemption.

Documentation quoting the literal check, scheme or an identified synthetic example
can be a non-secret match. Documentation containing a real copied credential is
still a leak. Unknown provenance, real credential material or production/staging
connection details fail the relevant required check or remain BLOCKED pending
classification. Follow existing security response policy within authority; no
credential validity probe, account change or scanner dismissal is implied here.

## Disposable regression cases for a fitted check

All values in a test fixture must be invented; never test with real secrets.

| Synthetic test case | Expected fitted-check treatment |
|---|---|
| postgres://ci:ci@localhost:5432/fixture_db plus inspected job-local disposable service and synthetic-only identity | May classify non-secret with scoped supporting evidence; no host/name wildcard. |
| Same literal, but service/identity provenance unknown | BLOCKED/unknown; the matching string alone cannot pass. |
| Invented production-like credential at localhost or fixture.localtest.me | Detect/reject under the test's simulated real-credential policy despite local host. |
| Docs quote only the literal postgres:// search term | Non-secret quotation; retain coverage of other candidates. |
| Docs contain an invented production-like URL/token | Detect/reject; documentation is not excluded. |
| Invented non-local/staging URL or unsupported/encoded credential syntax | Detect/reject or flag unknown according to the scoped check; never silently ignore. |
| One justified fixture match mixed with one simulated leak | Fail; a safe match cannot hide another candidate. |

These are test designs, not observations that any scanner or application passed.
Fit schemes, parsing/encoding and negative cases to the actual stack. Prefer an
exact reviewed fixture identity/context over path/host/user blanket exclusions;
ensure a changed credential, destination or service definition invalidates the
classification. Keep other secret patterns and repository policy in scope.

## Change the check honestly

If the old assertion incorrectly prohibited every connection-string-shaped value,
review the proposed task-specific criterion/procedure and synthetic positive and
negative tests. Hashed research/acceptance/phase changes need a synchronized reviewed
migration; do not silently edit contracts or reset all hashes. Preserve the old
FAILED result as history. Run the revised check on its exact new subject and record
fresh evidence before PASSED. A waiver stays WAIVED with its recorded result;
changing requiredness never makes the check pass. Optional checks remain the
user's choice and do not authorize external actions. Do not dismiss remote alerts
or change scanner configuration as a side effect of this guide.

Primary reference read 2026-10-30:
[GitHub secret-alert remediation](https://docs.github.com/en/code-security/how-tos/manage-security-alerts/manage-secret-scanning-alerts/resolving-alerts).
Confirmed leaks require the project's authorized response; a private repository
or an inactive token does not by itself make a leaked secret harmless.

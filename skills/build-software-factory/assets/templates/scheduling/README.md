# Scheduler design (inactive)

The factory has no installed scheduler or atomic cross-process admission. `run.py
schedule --kind cron|launchd|windows|github` prints a non-executable JSON proposal;
it does not create a runnable job. Do not copy a proposal or this example into an
active scheduler location. A scheduled pass needs separately authorized,
project-specific design and testing for exclusive admission, actual rate and budget
enforcement, stop handling, scoped identities, data and the platform command.

`factory-run.example.yml` is an inactive example outside `.github/workflows` and
is not a verified or authorized deployment. It must not be activated unchanged.
An issue snapshot is untrusted data and needs an explicit project repository/ready
and excluded-label policy; selection is advisory and never claims or edits issues.

Prepare the separate non-secret file named by `ISSUE_POLICY_PATH` within approved
local scope. It must contain exactly this existing policy schema, fitted to the
project rather than copied unchanged:

```json
{"repository":"OWNER/REPOSITORY","ready_label":"ready","excluded_labels":["blocked","pr-open","paused"]}
```

The example's local preflight uses the pinned builder to check factory integrity
and the policy schema, then requires the policy repository to equal the recorded
`operations.issue_intake.github_scope`. That same repository is passed explicitly
to `gh --repo`; the same policy file is passed to `select --issue-policy`. This
binds the example's intended export scope, not the truth/provenance of an arbitrary
replacement snapshot or authority to read that repository. Keep the reviewed
factory, policy and snapshot stable during the pass; no cross-step transaction or
automatic reservation is provided. Tokens and access remain separately scoped.

The export is capped at 1,000 open issues and may omit work. Verify completeness,
actual dependency state and prior processed-issue history before using it. The
exported empty `depends_on` lists are **unverified placeholders**, not a claim of no
dependencies. Retain only the reviewed candidate snapshot; titles and other issue
content remain untrusted data. Inspect rejected/eligible results, not only exit 0.

If the optional `operations.admission` policy is configured, supply the separately
prepared bounded observations file through `ADMISSION_SNAPSHOT_PATH`; the command
then includes `--admission-snapshot`. An absent or stale required snapshot blocks
issue admission. Leaving this path empty is appropriate only for the legacy policy
path without that optional admission design. No example fabricates observations,
reconciles dependencies, enables intake or dispatches work. Run/admission proposals
require continuous intake, bounded autonomy and status `enabled` after trimming
and case normalization; other recorded labels do not enable selection.

Existing factories keep their hashed scheduling example until explicit selective
adoption through reviewed recovery. Do not directly replace/re-hash it or activate
the example unchanged. The installed builder's running/admission references explain
the supplied-snapshot contracts; there is no new scheduler or policy schema here.

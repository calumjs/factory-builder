# Adopted operating improvements

These decisions are generic and task-dependent; they do not authorize external actions.

| Area | Adopted behavior and rationale |
| --- | --- |
| Integrity | Hash contracts; list and structurally validate five living files. Expected evidence/status edits no longer invalidate the contract baseline. Legacy manifests need reviewed migration. |
| Status and evidence | Preview-first helper updates task status and appends revision-bound evidence in one atomic JSON record. Passing supplied evidence and completed dependencies are required for `done`; evidence truth still needs review. |
| Windows text | Canonicalize BOM/line endings for contract hashing and ship local LF attributes. Substantive edits still fail integrity. |
| Python | Optional Windows launcher skips Store aliases, probes Python 3.9+ and reports the selected executable. It installs nothing and forwards the command once. |
| Repository hygiene | Provide optional ignore fragments and explicit staging guidance. Preserve root ignore policy and useful non-secret environment examples. |
| Acting identity | Record Git author and platform account/team/scope when relevant. Reject automatic identity/configuration changes and history rewrites. |
| Authentication | A PATH binary is insufficient. Record authorized read-only probe evidence; do not use paid or mutating calls as routine probes. |
| Headless operation | Record installed-version command, structured output, restrictions and auth recipe. Unverified providers remain disabled. |
| Autonomy | Model kill switch, submitter allowlist, rate/concurrency limits, rejection handling and budget. Missing bounded controls prevent live scheduling. |
| Versioned inputs | Resolve ambiguous latest-file candidates using version, revision and modification time. |
| External requests | Use tool-free extraction and deterministic validation with isolated restricted builders where exposed intake requires it. Treat prompts as data; prompting alone does not establish isolation. |
| Platform security | Prefer designs that retain deployment and permission protections. No automatic weakening of security controls. |
| Reviewer gates | Optional independent multi-reviewer policies require final-revision verdicts and bounded repairs. Additional providers need data/cost approval. |
| Visual conversions | Compare source exports with rendered pages and inspect worst mismatches. Similarity metrics supplement human visual, accessibility and functional checks. |
| Upstream contributions | Separate reusable-component provenance from application remotes, respect actual contribution policies and duplicates, and keep publication authority separate. Never infer merge authority. |

The research phase remains bounded and source-specific; practices are applied only to relevant phases. Offline integrity and schema checks do not prove research truth, application behavior or tool authorization.

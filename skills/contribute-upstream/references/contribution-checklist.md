# Contribution checklist

## Small local record
Use the existing authorized feedback log or a new approved local draft:
- Idea ID; affected component/version; verified upstream or unresolved candidates.
- Observation and sanitized evidence; hypothesis clearly labelled.
- Duplicate search terms/date/results/limitations.
- Issue vs PR vs existing-thread rationale.
- Proposed public title/body or focused diff.
- Privacy review, local validation and missing evidence.
- Required action/target/visibility and approval status.
- Result URL/revision or precise blocker; next owner.

No template file grants local write permission. Do not overwrite user-authored feedback.

## Public issue shape
Title: specific behavior or improvement, not a vague complaint.
Body: concise context about the reusable component; minimal synthetic reproduction; expected vs actual; relevant versions; observed impact; narrow proposal and alternatives; sanitized evidence; related issues. Avoid private application details and entire logs. If reproducibility is incomplete, say so.

## Focused PR shape
State problem, smallest change, linked issue when relevant, test evidence for the exact revision, compatibility/risks and limitations. Read the contribution guide before editing. Work on an authorized branch/worktree, preserve existing changes and avoid editing the user's installed plugin cache. Request authorization before a new remote fork/push if not already covered. Run relevant tests without inventing passes; unknown/blocked checks stay labelled. Open a draft PR unless the user requests otherwise. No approval, merge, branch protection change or deployment is implied.

## Privacy review before publication
Inspect the actual outgoing body, diff, attachments and links—not only a summary. Exclude credentials, cookies, environment dumps, customer identities, private repository paths/URLs, private source code and sensitive records. Replace evidence with a minimal synthetic reproduction. A private target also requires appropriate data-sharing authority. Confirm licensing/ownership permits sharing patches or examples; ask if uncertain. A secret scan is useful when available but not proof that a disclosure is safe. If a credential leak is discovered, do not paste it in an issue; surface the need for a separate private remediation process.

## Bounded standing authorization
An effective standing instruction names the target repository or verified set, permitted issue/PR/comment actions, content/privacy constraints, count/rate/time limit, and expiry or stopping condition. Record the instruction's provenance privately, not in the public issue. Scope or recipient changes require new approval. Credentials and repository membership are capability, not consent. Check limits before every write; a vague “improve things” is not unlimited publication permission.

## Failure and stopping
If repository identity, duplicate search, authentication, authorization or privacy cannot be established, preserve a draft and state the exact blocked action and missing decision. If a publish call times out, read/search for its result before deciding whether a retry is safe. Do not retry an uncertain mutation blindly. After confirmed submission, return the URL and stop unless follow-up was requested. Avoid unsolicited polling or recurring jobs.

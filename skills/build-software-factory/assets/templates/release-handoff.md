# Release handoff

Status: BLOCKED — no release authorization recorded.

Artifact and exact revision:
Target environment and deployed URL:
Accepted scope and acceptance evidence:
G1 pre-merge local smoke (production build) — revision / result / evidence: NOT RUN
G2 change-targeted tests — suite chosen and why / revision / result / evidence: NOT RUN
Other required checks and review decision:
Known risks and explicitly accepted exceptions (named human, scope):
Data changes / migration plan:
Rollback action and verification:
Human authorizer and exact approved action:
G3 post-merge confirmatory smoke against deployed URL — revision / result / evidence: NOT RUN
Post-release checks and stopping condition:
Actual result / evidence / time:

Handoff stays BLOCKED while G1 or G2 (or any other required check) is NOT RUN, BLOCKED or FAILED for the exact revision. Scaffold hashes and a successful host build are not substitutes. After merge/deploy, the release is unconfirmed until G3 passes; a G3 failure is surfaced to the release owner and triggers the rollback decision.

Preparation does not authorize publishing, merging or deployment.

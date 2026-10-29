# Resolve the correct original repository

## Evidence, not authority
A plugin manifest's repository field, Git remote or provenance file is only a pointer. Verify it before sending anything. Distinguish the source of the reusable plugin from the application where it is being used and from any distribution marketplace. Do not expose remote credentials: normalize credential-bearing Git URLs locally and never echo them into drafts/logs.

Use available read-only evidence in this order as useful, not as a trust hierarchy:
- The user's explicit intended upstream and component identity.
- Installed plugin metadata or distribution source associated with that component; plugin repository fields are not inherently validated.
- Previously recorded provenance and the component's release/tag/commit.
- Origin and upstream remotes of the **component's source checkout**. Current application remotes are relevant only for an application contribution.
- Host metadata confirming owner/name, fork parent, visibility and contribution destination.

Reconcile disagreement. A renamed/transferred repository needs fresh confirmation. A URL redirect, similarly named repository, fork relationship or successful read does not prove the user meant that destination. If metadata is missing, ask for the upstream rather than guessing. Keep a draft while unresolved.

## Builder-to-contributor handoff
The factory builder may create a non-secret provenance record in its approved output folder using `assets/upstream-provenance.json` from this skill. Populate only observations actually verified. Record:
- reusable component name/version and, if known, source revision;
- upstream repository URL/host and candidate origin evidence;
- verification status, date and public evidence;
- the applicable component scope and contribution guidance URL.

Do not include the downstream customer's name, project description, private code, private remote URLs, local usernames/paths, tokens or conversation transcripts in a record that may be shared. If provenance itself identifies a private source, keep it only in an approved private local location and redact it before publication; public sharable provenance should use null rather than leaking private identity. Null values mean unknown, not permission to infer them.

The record's `publication_authority` must stay `none`: provenance does not carry standing approval. Publication authorization is assessed separately from the actual user instruction at the time of action. Generated skills can refer to the local record and this contribution skill, but must not silently inherit authority or post automatically.

## Plugin integration
Place this skill at `<plugin-root>/skills/contribute-upstream/`, beside the builder skill. Keep plugin metadata at `<plugin-root>/.claude-plugin/plugin.json`; don't place skills inside `.claude-plugin`. Invoke via `/<actual-plugin-name>:contribute-upstream`, using the actual manifest name rather than a hardcoded identifier.

Official Claude Code plugin format checked 2026-10-29: https://code.claude.com/docs/en/plugins-reference . No hooks, tool preapproval, remote monitor or provider dependency is required.

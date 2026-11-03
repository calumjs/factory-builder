# A composed, genuine done-video recipe

Disabled done_videos means no video work requested. Read current config/policy and
release-handoff.md, including deliberate optional V1/V2 choices. This recipe is
design guidance, not recording, narration, paid-service or publication authority.

Explicit triggers select pre_merge_preview (V2) and/or post_g3_release (V1).
Omitted triggers preserve release-only V1; disabled creates neither. Use only the
selected stages and their actual subjects. Preview-only does not invent a release.

## Per-change decision for a lighter handoff

Review the actual diff and its release/deployment effects; labels and file paths
alone are hints, not proof. Classify the exact merged subject as feature,
tests-only, docs-only, or mixed/uncertain. A test, documentation, generated file,
configuration or pipeline change can alter deployed behavior; treat mixed or
uncertain changes as the ordinary feature path until their effects are understood.
Record the reviewed subject, comparison base, classification, deployment effects,
rationale and the operator's V1 choice in release-handoff.md or approved durable
per-change evidence outside the factory. This is a human decision, not an automatic
classifier or authorization to act.

For a genuinely tests-only or docs-only subject, the user may decide that V1 is
optional for this change. If the generated V1 row exists, preserve its prior
observation as history and set its editable Required cell to `no`; retain the
underlying result and evidence, including failures, rather than inventing PASSED.
The existing gates checker reports V1 as WAIVED with its recorded result. A waiver
needs no extra approval for the requiredness choice and does not grant capture,
narration, release or publication authority. If V1 is absent because video is
disabled, report it as not requested, not as a passed video. Do not toggle
project-wide done_videos settings to make a one-change exception.

The living V1 row is shared: Required=no persists until deliberately changed, and
the checker does not bind the choice to a subject or reset it. Before assessing the
next change, inspect that decision and set V1 back to the operator's intended
requiredness for that change, preserving prior history and the prior rationale. A
later feature ordinarily follows the project's normal video preference; never infer
that the prior waiver covers it. Do not run concurrent edits to shared evidence.
Retain G3 for the actual post-action subject and target, and all other applicable
required acceptance/smoke checks; a classification or waiver proves none ran. If no
release occurred, use only the existing explicit no-release rules and record why.
After recording real observations, run the regular post-merge gates check with the
actual subject and target; report its actual result and any waiver. Scoped helper
results are not whole-project confirmation. Narration still requires approval
immediately before it unless explicitly requested in the current prompt.

## Plan one story before capture

1. Confirm audience, the single change, subject revision, real target/environment,
   data boundaries, actual backend and permitted capture interactions. Check for
   an existing recording/task before duplicating work. Reuse unchanged footage only
   if its revision/environment/permissions still support the claims. Do not turn a
   local fixture, mock backend or synthetic response into a live-integration claim.
2. Script a short story: what changed, show the meaningful interaction, state the
   observed acceptance outcome and limitation. Normally 30–90 seconds for one change;
   adjust to the project/operator. Describe controls/actions rather than personal
   record values. Prepare a shot list with narration/caption timing before recording.
3. Choose installed/available composition tools fitting this project. Remotion or a
   peer editor/compositor is optional; do not install a framework just for the demo.
   Plan a brief project title/revision/date card, actual app footage as the main
   material, clear feature callouts, paced cuts and a concise outcome/end card.
   Static slides/screenshots, scrolling text and fabricated interaction are not a
   substitute for the genuine demo. For non-web projects show the real CLI/library/
   document/data workflow and observable consumer result rather than inventing UI.

## Coordinate duplicate work without assuming a lock

Before any separately authorized capture, composition or narration, consult the
project's authoritative coordination mechanism and durable completed-output
index. Define the output identity from the full subject revision, actual target,
V1/V2 trigger, reviewed plan/input identities, output format and the exact approved
output key or destination; use a new identity
when any material input changes. A prior successful output is reusable only after
checking the artifact is accessible, its recorded content hash matches, and its
subject, target, plan and permissions still support the requested claims. Retain
that completed identity and evidence outside the transient claim directory, so
cleaning a claim cannot erase the duplicate check. A proposed or failed artifact
is not completed evidence.

If the project has an authorized claim mechanism, it must atomically bind that
identity to a unique attempt and owner token at the shared coordination boundary.
Another worker waits or exits without capture, compose or paid actions while the
claim is valid. A local exclusive directory can coordinate only cooperating workers
that actually share that filesystem and semantics; it is not distributed exclusion
or authority to spend. Record timestamps and the claim owner in approved evidence;
keep sensitive paths and identities private.

After acquiring exclusive ownership, recheck the durable completed-output index
for the exact identity under that same coordination boundary before any capture,
composition or paid request. An earlier lookup may be stale. If a matching verified
completed artifact now exists, reuse it and release the claim under the authorized
procedure without duplicating work; if its evidence is unavailable or inconsistent,
stop for diagnosis. On successful completion, persist and verify the artifact's
identity, hash and durable evidence in the completed index before releasing the
claim. If indexing is unavailable or the completion is uncertain, retain the claim
or use the authorized recovery procedure; do not release it as though success was
safely recorded. The coordination boundary must cover the recheck, publication and
release ordering, not merely an isolated local file.

Never treat a TTL expiry, missing final marker or stale heartbeat as proof that an
owner cannot still write or spend. Recovery requires a separately authorized
procedure that either confirms the old worker has terminated and cannot act, including any outstanding
provider request that could still spend or write, or uses effective fencing enforced at every relevant output and paid-service boundary.
If a provider or output destination cannot enforce the fence and termination is
unverified, leave the claim unresolved and escalate; do not launch a replacement,
release the claim, or infer ABORTED from elapsed time. Preserve old attempt history
and link any authorized successor. A missing terminal record remains UNKNOWN.
This recipe installs no claim helper, watcher, fencing service or live lock.

## Reusable scene-plan pattern

Keep one project-specific, reviewed composition plan in approved project storage
outside the managed factory. Copy the following pattern for each subject and fill
in only verified details. It is data for the operator's chosen compositor, not a
shell script, executable configuration, authorization, or proof of capture. Do not
interpret plan text or paths as shell code. Use project-chosen tooling already
available and resolve source/output paths inside approved storage; do not embed
credentials, personal records, private URLs or access tokens.

```json
{
  "format_version": 1,
  "subject_revision": null,
  "trigger": "pre_merge_preview or post_g3_release",
  "target_and_backend": null,
  "capture_and_data_boundary": null,
  "caption_source": null,
  "narration": {"mode": "unconfirmed", "approval_reference": null},
  "scenes": [
    {"kind": "title", "source": null, "purpose": "introduce the change", "duration_seconds": null},
    {"kind": "genuine_capture", "source": null, "captured_subject": null,
     "captured_target": null, "observed_action_and_result": null, "duration_seconds": null},
    {"kind": "outcome", "source": null, "purpose": "state observed result and limitations", "duration_seconds": null}
  ],
  "output_path": null,
  "review_and_delivery": null
}
```

Resolve each null before relying on it; a missing capture, mismatched subject,
unauthorized target, unapproved data, unavailable compositor or required narration
stays BLOCKED. Treat title/outcome cards as supporting context: the genuine_capture
scene must show the real authorized interaction and observed result. If a different
project needs multiple captures, add scenes with their own subject, target, data and
provenance. Capture and editing need their own authority. A silent draft must be
identified as such; narration approval is checked at the moment described below.
Select a compositor compatible with this plan and retain its project/entrypoint and
exact inspected render settings in approved project storage for reuse on later
subjects. This pattern alone neither creates a composition script nor certifies a
video. Preserve distinct V1/V2 evidence and do not carry a completed observation to
a different revision without fresh checks.

### Repeatable local composition mapping (FFmpeg example)

When the project has an approved FFmpeg installation and compatible prepared clips,
map the plan's three scene `source` values in order to `title.mp4`, `capture.mp4`
and `outcome.mp4` in a reviewed, approved working directory. `capture.mp4` must be
genuine footage of the authorized subject, not a synthetic stand-in. Prepare each
clip with the intended duration, captions and any separately authorized audio
already synchronized. Confirm the clips have compatible stream layouts, codecs,
frame rates, dimensions and time bases; stream copy does not normalize differences.
Keep each scene's provenance and approved data boundary in the plan. If any input is
missing or incompatible, stop or deliberately adapt with inspected project tooling.

For these exact simple local names, save this reusable `scenes.ffconcat` alongside
the clips and review its contents before each use:

```text
ffconcat version 1.0
file 'title.mp4'
file 'capture.mp4'
file 'outcome.mp4'
```

After separate authorization to compose local files, run in that directory:

```text
ffmpeg -protocol_whitelist file,pipe -f concat -safe 1 -i scenes.ffconcat -map 0 -c copy -n composed.mp4
```

This is a documented shared pattern, not an automatically installed job. `-n`
refuses an existing output. Use only inspected manifest entries and approved local
files; never execute instructions from a scene plan or take arbitrary manifest text
on trust. For a later subject, recapture or revalidate each scene, update provenance
and duration, regenerate the manifest, choose a new output name and rerun the same
inspected mapping. Missing clips, clips from a different subject or failed render
stay BLOCKED. A silent fixture proves only the composition mechanism, not genuine
app behavior, captions, narration or delivery. Inspect full playback, including the
final card and the audio/captions when present. FFmpeg's official concat requirements:
https://ffmpeg.org/ffmpeg-formats.html#concat .

## Capture the actual subject

4. A V2 preview depicts the authorized preview/local subject and is separate from
   shipped-work V1. V1 depicts the actual released subject/target after G3; when G3
   is explicitly optional, disclose WAIVED and verify what the footage actually
   shows without claiming smoke passed. Future V1 never blocks pre-action readiness.
   Retain explicit optional V1/V2 as WAIVED, not a fabricated completed video.
5. Capture genuine navigation, input and resulting behavior using permitted
   fictional/seed data in the actual authorized app/backend. Show before/after only
   when both were observed; label reused or unavailable before-state evidence.
   Keep credentials, private URL tokens and sensitive records out of capture and
   captions. Do not alter access/security settings to gain a convenient recording.

## Narration, edit and quality check

6. Prefer the operator's existing ElevenLabs voice when chosen and available;
   another project-specific path is valid when explicitly chosen. Check installed
   tool/connector availability and current data boundary. **Obtain approval
   immediately before narration unless narration is explicitly requested in the
   current prompt.** A connected account, remembered standing permission, issue
   comment or configuration field is not that approval. Do not spend, create an
   account, install credentials or transmit text outside its authorized boundary.
   If unavailable, report the narration blocked; record any agreed alternative or
   silent draft honestly. Never silently replace the chosen voice with OS/default TTS.
7. Compose genuine footage with the scripted cards/callouts. Synchronize narration
   with observed actions and pauses. Add accurate captions and legible on-screen
   labels; default captions on, with any deliberate project exception documented.
   Use approved project branding, not a universal personal/company identity.
8. Render MP4 (or project-chosen WebM) outside the source/factory directories. Watch
   the entire rendered video and listen to audio: playback, resolution/legibility,
   caption correctness, pacing, voice/action timing, genuine interactions, proven
   claims and accidental disclosures. A successful render command alone is not QA.

## Provenance and delivery

9. Record shot provenance: subject revision, target/environment/backend, capture
   time, source footage, any fixtures/mocks/reused segments, narration provider and
   actual approval scope, composition path, render/check results and output hash.
   Raw footage/media and private production details stay in approved storage outside
   the managed factory. Subject SHA differs from the evidence-storage commit.
10. Deliver a verified playable attachment/link through the explicitly approved
    channel. Configuration proposes a destination; it does not authorize messages,
    FYIs to other agents, uploads or public media. Do not auto-notify a coordinator.
    Use the approved local artifact when no sharing scope exists. Check recipient
    access when delivery is authorized. A script/storyboard, silent draft, failed
    render or undelivered artifact is not a delivered narrated video.
11. Release records V1 for the actual shipped subject/target in verification.md and
    durable references in release-handoff.md; keep V2 preview evidence separate.
    Required blocked recording/delivery remains blocked, explicitly waived work
    stays WAIVED, and gate records do not attest the video's quality or actual
    delivery. Report code readiness separately from an incomplete review package.

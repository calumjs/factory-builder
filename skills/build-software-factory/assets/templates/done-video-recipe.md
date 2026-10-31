# A composed, genuine done-video recipe

Disabled done_videos means no video work requested. Read current config/policy and
release-handoff.md, including deliberate optional V1/V2 choices. This recipe is
design guidance, not recording, narration, paid-service or publication authority.

Explicit triggers select pre_merge_preview (V2) and/or post_g3_release (V1).
Omitted triggers preserve release-only V1; disabled creates neither. Use only the
selected stages and their actual subjects. Preview-only does not invent a release.

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
    {"kind": "title", "purpose": "introduce the change", "duration_seconds": null},
    {"kind": "genuine_capture", "source": null, "captured_subject": null,
     "captured_target": null, "observed_action_and_result": null, "duration_seconds": null},
    {"kind": "outcome", "purpose": "state observed result and limitations", "duration_seconds": null}
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

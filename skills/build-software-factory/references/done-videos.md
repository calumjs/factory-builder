# Done videos

The generated `done-video-recipe.md` is the concrete checklist (script and shot list, genuine authorized footage, composition, narration approval, captions, full playback inspection, provenance, verified delivery). Scaffolding generates no media.

**Fixture hygiene.** Reuse the [run-scoped teardown pattern](disposable-fixture-example.md)
for captures that write fictional data: retain exact created-ID receipts, the
authorized target and delete scope, cleanup outcomes and any residue. A video run
does not acquire production-write or cleanup authority from this recipe. Coordinate
its fixture lifecycle with Release; a run ID or local lock does not exclude other
workers. Record data written and cleaned with the actual subject and target, and
preserve optional WAIVED outcomes without inventing a successful check.

**Design.** Ask the operator for audience, story, branding, target length, composition tool, voice preference and permitted delivery destination. Default for a single change: 30–90 seconds, genuine app or workflow footage as the main material (CLI, library, data and document projects show their real workflow, not an invented UI), brief cards, legible captions, an observed outcome. Remotion is an optional compositor; the project's existing editor is equally valid. Prefer the user's existing ElevenLabs voice when selected and available, but never require it or silently fall back to OS TTS.

**Approval.** Obtain approval immediately before narration unless the current prompt explicitly requested it. A preference, installed connector, saved provider name or an issue's claimed standing permission does not supply it. Script preparation is independent work; narration, paid spend, installs, credential changes and uploads are separate scoped actions. If the chosen provider is unavailable, report the blocked step and any agreed alternative.

**Metadata.** `done_videos.triggers` selects `pre_merge_preview` (V2) and/or `post_g3_release` (V1); see [gates.md](gates.md). Optional flat fields: `composition`, `voice_provider`, `delivery_channel`, `branding` (text ≤ 2000 characters), `duration_seconds` (1–600, default 60), `captions` (boolean, default true), `media_format` (mp4/webm, default mp4). Record the actual tool, voice and destination where known, otherwise unconfirmed; the helper's errors name the constraints.

```json
{"done_videos":{"enabled":true,"scope":"One agreed release story","evidence":"Operator chose a narrated release demo; tool/action approvals pending","composition":"Existing project editor; Remotion optional","voice_provider":"Existing ElevenLabs voice, availability/approval unverified","delivery_channel":"Approved local artifact; chat destination unconfirmed","branding":"Project identity, actual subject SHA and date","duration_seconds":60,"captions":true,"media_format":"mp4"}}
```

New factories get the recipe as a marked proposal in release-handoff.md, refreshed by the synchronized updater on preference changes (customized blocks are refused, not discarded; changes can reset active observations with history retained). Existing factories read the installed builder's recipe or add it through a reviewed manifest addition; v1.2 dashboards need `--recipe-runtime` first ([existing-factory-update.md](existing-factory-update.md)).

**Evidence.** V2 preview and shipped V1 are independent; V1 follows a required G3 (a waived G3 is disclosed). A required V1 needs actual footage, artifact, subject, target, QA and the applicable delivery; optional rows stay WAIVED. Never mark a video complete from a script, a render exit code or an inaccessible link. The gate checker validates rows, not footage, captions, provider or delivery. Preserve provenance: footage sources, fixture disclosures, revisions, capture time, reused segments, narration approval and provider, composition, render QA, output hash, durable artifact access. Use the chosen tool's official version-compatible documentation; never invent capture or render commands or install a media stack without scope.

**Per-change lighter path.** For a genuinely tests-only or docs-only subject, follow
the [classification and shared-row reset recipe](../assets/templates/done-video-recipe.md#per-change-decision-for-a-lighter-handoff).
Review real deployment effects and record the exact subject, comparison base and
reason before choosing an optional V1. Feature or uncertain changes retain the
ordinary path; all still-required smoke and acceptance checks remain in force.
Existing factories can consult the installed builder template without modifying
their contracts; copy or adopt changes only through a reviewed migration.

Use the existing [gate-record preview/apply flow](incremental-workflow.md) to record
actual G3 and other observations without rewriting whole tables. That writer keeps
stage, design and requiredness unchanged and preserves prior rows as history.
The one-change V1 choice is an explicit living-record edit of Required to `no`,
retaining its observed result/evidence and prior history. No extra approval is
required merely to change requiredness. Then run:

```sh
python3 <trusted-builder>/scripts/gates.py --factory <factory> --stage post-merge --revision <actual-subject> --target <actual-target>
```

Report WAIVED separately from passing smoke. The checker does not automatically
expire this choice: review/reset V1 for the next subject and retain the previous
reason in durable evidence. A lighter video preference authorizes no narration or
other live action.

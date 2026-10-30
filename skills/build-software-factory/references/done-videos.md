# Done videos

The generated `done-video-recipe.md` is the concrete checklist (script and shot list, genuine authorized footage, composition, narration approval, captions, full playback inspection, provenance, verified delivery). Scaffolding generates no media.

**Design.** Ask the operator for audience, story, branding, target length, composition tool, voice preference and permitted delivery destination. Default for a single change: 30–90 seconds, genuine app or workflow footage as the main material (CLI, library, data and document projects show their real workflow, not an invented UI), brief cards, legible captions, an observed outcome. Remotion is an optional compositor; the project's existing editor is equally valid. Prefer the user's existing ElevenLabs voice when selected and available, but never require it or silently fall back to OS TTS.

**Approval.** Obtain approval immediately before narration unless the current prompt explicitly requested it. A preference, installed connector, saved provider name or an issue's claimed standing permission does not supply it. Script preparation is independent work; narration, paid spend, installs, credential changes and uploads are separate scoped actions. If the chosen provider is unavailable, report the blocked step and any agreed alternative.

**Metadata.** `done_videos.triggers` selects `pre_merge_preview` (V2) and/or `post_g3_release` (V1); see [gates.md](gates.md). Optional flat fields: `composition`, `voice_provider`, `delivery_channel`, `branding` (text ≤ 2000 characters), `duration_seconds` (1–600, default 60), `captions` (boolean, default true), `media_format` (mp4/webm, default mp4). Record the actual tool, voice and destination where known, otherwise unconfirmed; the helper's errors name the constraints.

```json
{"done_videos":{"enabled":true,"scope":"One agreed release story","evidence":"Operator chose a narrated release demo; tool/action approvals pending","composition":"Existing project editor; Remotion optional","voice_provider":"Existing ElevenLabs voice, availability/approval unverified","delivery_channel":"Approved local artifact; chat destination unconfirmed","branding":"Project identity, actual subject SHA and date","duration_seconds":60,"captions":true,"media_format":"mp4"}}
```

New factories get the recipe as a marked proposal in release-handoff.md, refreshed by the synchronized updater on preference changes (customized blocks are refused, not discarded; changes can reset active observations with history retained). Existing factories read the installed builder's recipe or add it through a reviewed manifest addition; v1.2 dashboards need `--recipe-runtime` first ([existing-factory-update.md](existing-factory-update.md)).

**Evidence.** V2 preview and shipped V1 are independent; V1 follows a required G3 (a waived G3 is disclosed). A required V1 needs actual footage, artifact, subject, target, QA and the applicable delivery; optional rows stay WAIVED. The gate checker validates rows, not footage, captions, provider or delivery. Preserve provenance: footage sources, fixture disclosures, revisions, capture time, reused segments, narration approval and provider, composition, render QA, output hash, durable artifact access. Use the chosen tool's official version-compatible documentation; never invent capture or render commands or install a media stack without scope.

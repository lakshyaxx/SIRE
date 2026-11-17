# V4.5 frontend/API handoff

Launch from repository root with `.\.venv\Scripts\python.exe scripts/dev.py`; default local URL is `http://127.0.0.1:8000`. `SIRE_STATE_DIR` selects state before import; defaults to `.runtime/v2`. `SIRE_WEB_BUILD` permits `dist` or `dist-v3`. Production uses `dist`; QA used port8001 and `.runtime/v45/qa`. Never point test fixtures at production state.

Generated [OpenAPI](V45_OPENAPI.json) is the source of exact REST schemas; `/docs` and `/openapi.json` are served locally. `GET /api/v1/health` includes `application_version`, `loaded_source_sha256`, installed provider readiness and native `ml_ready`. QA explicitly disables native startup probing, so its false `ml_ready` does not imply no working prediction routes. Main startup probes a genuine native sample.

## Chat and background jobs

Use the actual `web/src/lib/api.ts` helpers. POST `/api/v1/chat/message` takes `conversation_id`, unique `request_id`, `content`, `attachment_ids`, `mode` and optional typed context/model/prediction linkage. `voice_response:true` selects the short voice profile. `background_if_deep:true` opts into JSON202 dispatch for deep work; existing ordinary callers still get SSE.

202 response: `{type:"investigation_job",job:<InvestigationJob>}`. It is an acknowledgement of persisted work, not an assistant completion. Explicit Investigate can POST directly to `/api/v1/investigation-jobs` with the same request body. Poll list/get with `conversation_id`; cancel the selected job with POST `/{id}/cancel?conversation_id=...`. Reuse an identical request ID/body for idempotent retry; changed body409. Wrong conversation404; active-per-conversation409; global capacity429.

Lifecycle: queued/running/complete/partial/error/cancelled/interrupted. Recent actual events are bounded; inspect `events_total`/`events_trimmed`. `run_id` links `/runs/{id}/trace`; `assistant_message_id` links the exact stored reply. Ordinary SSE terminal events also carry the exact assistant ID. Never auto-play an older answer after a202.

Verified early facts are only delta events with source `validated_descriptive_measurement_statistics`; progress/status strings are not diagnostic findings. Use `case.recall`/`investigation.status` through ordinary chat for saved decisions and actual progress. They do not rerun proposals.

## Attachments, citations and reports

POST `/attachments` with real FormData `conversation_id` and `file`. Do not set Content-Type manually. Snapshot the picker FileList before clearing it or awaiting; preserve actual File bytes. Check durable receipt/evidence IDs and explicit media errors. `metadata.original_sha256` authenticates uploaded bytes against the receipt; `sha256` may identify sanitized content. Synthetic industrial telemetry is not NASA-compatible without validated genuine schema/data.

Sources resolve at `/evidence/{id}` and actual bytes at `/attachments/{id}/content`. Display original locators, units, asset/time and limitations. Clickable source IDs are not proof of support. Inspector keeps typed verification and actual trace results.

POST `/evidence-investigations/{case_id}/report`, then GET `/reports/{report_id}/download?format=pdf|markdown|json`. PDF/Markdown contain readable bounded exact source previews. JSON contains the complete immutable case/evidence snapshot, including every original row. Report IDs include format2.1; old exports are not overwritten. Physical/human review remains unreviewed until actually performed.

## Live voice and inline playback

`GET /voice/session-schema` describes the transport. Connect same-origin `ws://127.0.0.1:8000/api/v1/voice/session?conversation_id=...` after an explicit microphone Start gesture. Only PCM16 little-endian mono16kHz binary frames, maximum32768bytes; maximum600seconds, one active session, two queued final utterances. JSON controls are `{op:"flush"}`, `{op:"reset"}`, `{op:"close"}`. Origin/cid/capacity checks are enforced.

Actual events: ready, speech_started, transcribing, transcript, error, closed. Final transcript contains attachment/turn/VAD evidence IDs, real model/provider and limits. Whisper does not stream partial words. Browser worklet frames are converted to exact bounded PCM; sample-rate mismatch is refused, not mislabeled. The Start session explicitly enables automatic unverified final-transcript sending. Manual review-first recording remains available. Stop all tracks/context/socket on navigation, disconnect, error or Stop.

Speech uses POST `/voice/speak` with text and unique request_id; it returns real WAV with `X-Speech-Model` and frame headers. POST `/voice/cancel` stops the exact owned request. InlineSpeech prepares one next chunk, plays via browser Audio, and supports pause/resume/stop. It is chunked whole-WAV synthesis, not streaming neural PCM. Physical microphone permission, autoplay, audibility and barge-in require manual browser acceptance; automation host was unavailable. Do not auto-accept privacy/security prompts.

## Verification commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=short
.\.venv\Scripts\python.exe -m ruff check app scripts tests
.\.venv\Scripts\python.exe -m black --check app scripts tests
cd web
npx tsc --noEmit
npm test
npm run build
```

For repeatable isolated acceptance, launch `qa_server:create_qa_app` from `.runtime/v45` on8001 with the documented QA state/build; run `scripts/v45_smoke.mjs` against the public corpus and a fresh V45 output path. `scripts/v45_acceptance.py --help` lists real network/voice/native/negative/cancel checks. `scripts/v45_offline_acceptance.py` creates its own fresh disposable state and process-only network guard. Keep previous proof directories immutable and choose a fresh namespace for reruns.

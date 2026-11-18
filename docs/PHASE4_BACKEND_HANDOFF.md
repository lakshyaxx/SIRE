# Phase 4 backend handoff

Start the existing local app with `.venv/Scripts/python.exe scripts/dev.py`; production4.7.0 is running at http://127.0.0.1:8000 after read-only verified cutover. Preserve `.runtime/v2`, protected artifacts, frozen results and the external root environment. No Phase 4 frontend redesign or new complete voice-call UI was implemented in Phase 3.

## Stable actual contracts

Application4.7.0; main contract2.0; specialist discovery1.0. Live `/openapi.json` resolves all component references. Read `/api/v1/specialists/contracts` for actual argument/output schemas and namespace identity; do not infer fields from these notes. Existing [Phase 2 API details](PHASE2_API_CONTRACTS.md) remain compatible. New GeneratedAudio lifecycle/fallback/model_reused fields are additive and optional.

| Interface | Integration |
| --- | --- |
| POST `/api/v1/attachments` | Multipart conversation_id + original file; retain actual receipt ID/hash |
| POST `/api/v1/chat/message` | Existing conversation_id/request_id/content/attachment_ids and optional input provenance; SSE started/plan/tool/evidence/delta/report/done |
| POST `/api/v1/investigation-jobs` | Durable background investigation; poll/cancel owned job, retain real run ID |
| POST `/api/v1/specialists/speech/stream` | conversation_id, unique request_id, text, voice_id0, speed1; completed-sentence WAV SSE |
| POST `/api/v1/specialists/cancel` | Exact conversation_id + active request_id; stop current owned specialist work |
| POST `/api/v1/voice/transcribe` | Original recording upload; default Whisper base, explicit profile=asr tiny |
| GET `/api/v1/voice/session-schema` | Actual PCM bounds/control schema/events |
| WS `/api/v1/voice/session?conversation_id=...` | Origin-checked PCM16LE mono16kHz; final VAD utterance transcripts |
| GET `/api/v1/runtime/resources` | Existing local scheduler, owned CPU worker snapshots and real Ollama residency |
| GET `/api/v1/runs/{id}/trace` | Actual persisted tool and provider provenance |

Text: render progress/evidence as received. Engineering model commentary is buffered until source-reference checks finish; provider first token is not display TTFT. Fast greetings/capability/saved recall avoid the LLM. Keep text and reviewed speech content on the same routing path; transcripts are input provenance, not external engineering proof. Do not force greetings into evidence investigations.

Audio: `started` identifies actual run/segment count. Each `audio_chunk` contains index and actual `audio` WAV/base64/hash/frames/rate/model/voice/speed/cache/lifecycle fields. Decode complete WAVs into queued local playback in index order; `done` gives complete/cancelled/error and delivered count. Existing bounds160characters/segment,10segments, overall1200characters. These are complete-sentence chunks, not streaming neural waveform frames. First fresh WAV measured 12.881s; exact cached replay 0.244s. Never present cached time as fresh inference.

Stop: abort fetch/playback and issue exact scoped specialist cancel; job and chat cancellation retain their respective owned IDs/routes. A disconnect also cancels owned streaming work. Deliberate user interruption must stop playback, reset capture state and cancel the active response before submitting a new reviewed turn. Observed active speech cancel 0.020s; active GPU cancel 0.308s. Do not kill Ollama by name or cancel on every VAD candidate.

Microphone: require explicit user activation; use `/voice/session-schema`, bounded binary PCM and permitted controls flush/reset/close/client_event. Receive ready/speech_started/transcribing/transcript/error/closed. Whisper returns final utterances, **no partial-word ASR**. Preserve recording/source IDs; review/edit transcript before chat. Browser must suppress mic frames during playback/cooldown. Client-event telemetry does not enforce physical echo cancellation by itself. Speech onset is only a candidate; explicit Interrupt-and-speak is the current dependable design. Do not turn recorded spoken commands into executable controls.

## Remaining acceptance and performance work

Physical browser/microphone/speaker acceptance, measured audible onset, noisy-room/feedback, deliberate natural barge-in and subjective pronunciation/naturalness remain unverified. Earlier CUA browser access was blocked by tool security; no bypass attempted. Do real authorized device testing inPhase 4 and record browser/device/rate/playback timing. Existing frontend unit tests are not physical acceptance.

CPU Kokoro remains slower than realtime on long new text; after idle/model switches cold setup returns. One heavy slot can queue model-based conversation during an investigation; deterministic controls stay responsive. Actual latest fresh deep investigation 29.565s, paired 22.822s; no latency SLA. ASR has technical word errors and requires review. Causal hypothesis accuracy and qualitative citation entailment need independent review; one real generated fragment is now honestly flagged. Keep strict source checking and original files. New providers/models, audio UI redesign or artifact cleanup require separately scoped decisions.

Read [release readiness](PHASE3_RELEASE_READINESS.md), [voice performance](PHASE3_VOICE_PERFORMANCE.md) and [test results](PHASE3_TEST_REPORT.md) before declaring any full voice or industrial diagnostic acceptance.

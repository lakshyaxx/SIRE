# Phase 2 API contracts

Application4.6.0, existing contract2.0. Additive specialist discovery contract1.0. Generated actual [OpenAPI snapshot](PHASE2_OPENAPI.json); live http://127.0.0.1:8000/docs. Internal schema references validated with zero missing components. Per-tool actual input/output schemas are returned by `/api/v1/specialists/contracts`; consult them rather than guessing arguments.

| Method / endpoint | Purpose / actual contract |
|---|---|
| GET `/api/v1/health` | Runtime/source fingerprint, installed tags and native readiness |
| GET `/api/v1/providers/registry` | Local model/provider availability, quantization, digests, explicit unmeasured resource fields |
| GET `/api/v1/runtime/resources` | Existing heavy scheduler and actual Ollama residency |
| POST `/api/v1/attachments` | Existing multipart upload: `conversation_id`, file bytes; actual receipt/source IDs |
| GET `/api/v1/specialists/contracts` | Actual tool JSON schemas and state namespace fingerprint |
| POST `/api/v1/specialists/execute` | Typed envelope: conversation_id, request_id, tool_id, arguments |
| POST `/api/v1/specialists/cancel` | Scoped conversation_id + request_id; whether active cancellation requested |
| POST `/api/v1/specialists/speech/stream` | conversation_id, request_id, text, voice_id(default0), speed(default1); genuine sentence WAV SSE |
| POST `/api/v1/specialists/retrieval/rebuild` | conversation_id + request_id; clear only owned derived vectors, lazy next-query rebuild |
| POST `/api/v1/voice/transcribe` | Existing actual recording endpoint; optional `profile=asr` selects preserved tiny model explicitly |
| POST `/api/v1/chat/message` | Existing actual SSE text/tool/evidence results |
| POST `/api/v1/investigation-jobs` | Existing durable investigation request; poll/cancel endpoints remain |
| GET `/api/v1/runs/{id}/trace` | Actual persisted plan/tool/provider trace |
| GET `/api/v1/evidence/{id}` | Canonical evidence/alias inspection |

Whitelisted specialist IDs: `vision.inspect`, `audio.transcript`, `speech.synthesize`, `document.extract`, `measurements.profile`, `video.frames`, `video.inspect`, `knowledge.retrieve`, `prediction.run`. Other existing orchestration tools remain internal, not arbitrarily dispatchable by this endpoint.

Example request from the **disposable QA** evidence IDs (not production IDs; use8001 only when the matching QA server is intentionally running):

```json
{
  "conversation_id": "d7b2ce063b6d4336b3cf2c6748505bab",
  "request_id": "phase2-handoff-example",
  "tool_id": "knowledge.retrieve",
  "arguments": {
    "text": "maintenance evidence",
    "mode": "hybrid",
    "attachment_ids": [
      "eee6b115609a456e899a0486fe013523"
    ]
  }
}
```

Response fields: `request_id`, genuine persisted `run_id`, `tool_id`, `status`(complete/cancelled/error), measured `elapsed_seconds`, `output_role`(observations/input_provenance/generated_audio), validated tool `output`, resolvable `evidence_ids`, explicit `error`, provider/model/digest/execution `provenance`, and `limitations`. Output schemas preserve compatible legacy fields. `audio.transcript` has no engineering evidence list; cached extraction provenance is labeled cached. HTTP errors preserve actual validation/provider failure status; early invalid/scope errors use the existing SIRE error envelope. No dummy result on failure.

Speech SSE `data:` objects: `started`(run_id,segments,streaming_mode), `audio_chunk`(index,actual base64WAV/hash/frames/rate/model/voice/speed/cache/resources), optional `error`, terminal `done`(status,delivered_segments,elapsed_seconds). Completed-sentence WAV delivery is not raw token/audio-frame realtime generation. Max160characters per chunk and10chunks; existing overall text/voice/speed bounds remain. Disconnect/Stop cancels the active owned worker. Frontend teams can consume these contracts without a visual redesign.

Retrieval: modes auto/lexical/semantic/hybrid, optional owned attachment_ids and timezone-aware as_of; fixed local index fingerprint. Auto selects semantic only if lexical finds no hits. Rebuild removes derived embeddings only, never original documents. Similarity remains unverified relevance.

Failure examples actually exercised: wrong conversation/attachment scope; malformed/image-only PDF422; nonexistent Ollama tag; refused local endpoint; duplicate active request409; provider/model hash errors; active cancellation. Use the actual OpenAPI schemas for remaining legacy audio/session/job request details.

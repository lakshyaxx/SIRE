# Actual frontend API mapping

All calls use the same origin and `/api/v1`. `lib/api.ts` owns HTTP/error/SSE transport; `services/api.ts` adapts actual backend records to delivered view types. No invented `/v1` implementation or fabricated response cache remains.

| UI feature | Existing real contract / additive index |
| --- | --- |
| Configuration/readiness | GET `/health`, `/providers`, `/voice/capabilities`, `/frontend/config` |
| History | GET/POST `/conversations`; GET/PATCH/DELETE `/conversations/{id}` with existing delete confirmation |
| Chat | POST `/chat/message` SSE; POST `/chat/cancel` scoped to conversation/request |
| Upload | POST `/attachments` multipart (`file`, `conversation_id`); actual ingestion status and attachment ID |
| Documents | GET `/knowledge/sources?conversation_id=…`; POST `/knowledge/ingest`; exact chunk locators retained |
| Background investigations | POST/GET `/investigation-jobs`; actual job ID, request ID, conversation ID and events; POST `/{id}/cancel?conversation_id=…` |
| Saved findings | GET `/frontend/investigations` and `/{id}` over actual `cases` and `v45_jobs`; job/case alias resolves real report |
| Export | Actual saved case GET `/evidence-investigations/{case_id}/report?format=pdf` |
| Source library | GET `/frontend/attachments` and `/{id}`, bounded SQL pagination/search/modality; no private filesystem paths |
| Canonical evidence | GET `/evidence/{id}`; `evidence.pointer.attachment_id` identifies original; GET `/attachments/{id}/content` previews/downloads |
| Predictions | GET `/predictions/datasets`, `/predictions/models`, real asset telemetry; POST `/predictions/upload`, `/predictions/run`, `/predictions/compare`, `/predictions/anomaly`; prediction ID follows into chat |
| Voice | GET `/voice/session-schema`, WebSocket `/voice/session`; actual existing transcription/synthesis and playback routes retained |
| Scenarios | Retained real `/scenarios`, asset/history/dependency, investigation, prior-case, fleet, what-if and report interfaces in Engineer controller |
| Registry | `/models` native catalog plus `/specialists/*` runtime/contracts/readiness |

Actual states include queued/running/complete/partial/error/cancelled/interrupted. Stored completion means the computation finished; it does not verify a physical diagnosis. Hypothesis order, source IDs and contradiction groups are preserved. No confidence percentages are synthesized. Missing source sizes/timestamps remain unknown. Case history's source count reflects report observations, not an invented number of uploaded files.

Transport has bounded requests, caller cancellation, CRLF/UTF8 SSE buffering and a required actual terminal event. A disconnected stream is an error. Uploads clear on real acknowledgement; a failed extraction never silently starts a job. GET indexes do not invoke inference or mutate application data.

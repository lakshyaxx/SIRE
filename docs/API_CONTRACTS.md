# Additive V3 API contracts

Existing /api/v1 chat, conversation and prediction contracts remain. New endpoints use explicit scenario/asset/time scope; OpenAPI remains authoritative.

| Route | Actual behavior |
| --- | --- |
| GET /capabilities | Bound typed tools and current provider/source availability |
| POST /intelligence/execute | Whitelisted schema-validated tool call with persisted trace; no arbitrary SQL/code |
| POST /evidence/upload, GET /evidence/{id}?as_of= | Private validated source snapshots and exact resolver with optional historical availability check |
| GET /scenarios, /scenarios/{id}, /scenarios/{id}/assets | Generated observable metadata, no truth labels |
| GET /assets?scenario_id=, /assets/{id}/telemetry, /assets/{id}/relations | Scoped raw rows, units and directed valid edges; both observed/available fences |
| GET /incidents/{scenario_id}/timeline?as_of= | Available event chronology only |
| POST /facility/investigations | Bounded genuine graph/analytics/rule case; accepts request_id for cancellation |
| POST /facility/investigations/{request_id}/cancel | Signals an active job; no downstream tools after cancellation |
| GET /cases, /cases/{id}, /cases/{id}/similar | Preserved provisional cases, revisions and explained overlap; historical memory checks creation availability |
| POST /cases/{id}/continue, /cases/{id}/annotations | New case revision / separate unverified manual review, never source mutation |
| GET /fleet/overview?scenario_id=&as_of= | Actual quality/missing/trend indicators, not failure probabilities |
| POST /simulations/what-if | Synthetic-only service_hour/load_factor, identical seed and cutoff-fenced trajectories |
| POST /cases/{id}/report, GET /reports/{id}, /reports/{id}/download?format=markdown-or-pdf | Frozen source snapshot, integrity metadata and genuine report bytes |
| GET /runs/{id}/trace | Privacy-safe plan, real tool starts/ends, status and evidence IDs |
| GET /voice/capabilities, POST /voice/transcribe, /voice/speak | Accurate unavailable state; PCM validation then specific ASR/TTS 503, no fake audio |

Synthetic seeding is a local CLI/startup operation, not an unauthenticated HTTP reset. All source classes stay separate. Canonical V3 upload originals/excerpts retain local audit history; no deletion of those records is advertised. A normal V2 confirmed chat deletion retains its existing semantics. Local multi-user auth and hosted providers are not implemented; services bind loopback.

---

# V2 API contracts

Base `/api/v1`. Request schemas are authoritative at `/openapi.json` and `/docs`; matching checked TypeScript types/transport live in `web/src/lib/api.ts`. Pydantic validates requests. Response dictionaries are integration-tested rather than a generated client. Errors contain `error.code`, `message`, `details`, `request_id`; raw inputs and stack traces are withheld.

| Method / path | Behavior |
| --- | --- |
| GET `/health`, `/providers` | API/ML probe, installed local-model readiness, lexical retrieval disclosure |
| GET/POST `/conversations` | List/create persistent chats |
| GET/PATCH/DELETE `/conversations/{id}` | History, rename, deletion with `confirm=true` |
| POST `/attachments` | Multipart conversation + file; optional declared dataset/domain for CSV |
| GET `/attachments/{id}/content` | Stored safe/normalized attachment content |
| POST `/chat/message` | `conversation_id`, content, optional attachment IDs, request ID, mode, installed model, explicit prediction ID |
| POST `/chat/cancel` | Request ID; whether an active job was signalled |
| GET/POST `/investigations` | List saved cases / rerun exact server-collected evidence |
| GET `/investigations/{id}` | Saved structured case |
| GET `/predictions/datasets` | FD001–FD004 with actual source assets |
| GET `/predictions/models?dataset=FD003&purpose=rul` | Native model identity, recorded inference status, exact-run historical metrics |
| POST `/predictions/run`, `/predictions/anomaly` | Explicit dataset/model, exactly one asset or compatible CSV ID; separate output semantics |
| POST `/predictions/compare` | Same source, 2–4 selected models, individual results/errors |
| POST `/predictions/upload` | Independent CSV + dataset + compatibility declaration; no chat required |
| GET `/predictions/uploads/{id}/telemetry?dataset=FD002` | Revalidated uploaded sequence |
| GET `/predictions/assets/{dataset}/{asset_id}/telemetry` | Actual matched source readings |
| GET `/predictions/results/{id}` | Saved attachable prediction |
| POST `/knowledge/ingest`, GET `/knowledge/sources?conversation_id=...` | Local document intake and exact passages |

Prediction results carry saved ID, dataset/model/source, operating cycles, native interval/method if available, separate anomaly output, window warnings, target policy, seed/version/hash and provenance. Missing/mismatched sources fail. No FD001 fallback. Anomaly scores and raw legacy quantiles keep their original semantics. A declared compatible CSV still does not establish linkage to a photograph.

Chat sends SSE `data: {JSON}\n\n`: started, tool, evidence, delta, report, error, done. Normal deltas are real provider tokens. Structured investigations deliver a report after actual tool execution. Errors/cancellation persist. Cancelling an active synchronous tool may wait for it to finish; no subsequent tools start. A disconnected client may receive a closed stream without done.

Limits: 10,000,000 upload bytes; six attachments/three images per turn; UTF-8 text; PDF at most 40 pages and bounded extraction; single-unit, finite, ordered 26-column compatible C-MAPSS input; 10,000 history rows. Clients cannot submit loader paths. No hosted adapters are enabled. Read-only `/api/health`, `/api/models`, `/api/v1/models` aliases remain; the retired V1 frontend is not served.

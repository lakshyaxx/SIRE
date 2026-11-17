# API contract v1

Interactive authoritative schemas: `/docs`; machine schema: `/openapi.json`. All errors use `{error:{code,message,details,request_id}}`. User text and private paths are not reflected in error details.

| Route | Contract |
| --- | --- |
| GET /api/health | Service alive; actual startup ML probe and live loopback Ollama status |
| GET /api/models | `models`: 44 registered dataset/family/seed/task routes with provenance and smoke status |
| GET /api/assets?dataset=FD001 | Source-derived assets from official test sensor rows |
| GET /api/assets/{id}/telemetry?dataset=FD001 | Actual raw cycle/settings/sensor records and source path |
| POST /api/data/upload | Multipart `file`, optional `dataset`, `compatible_cmapss`; UTF-8 CSV preview and eligibility |
| POST /api/rul/predict | JSON `dataset`, `model_id`, exactly one of `asset_id`/`upload_id`; native estimate/provenance/limits |
| POST /api/rul/compare | Same source/dataset plus 2-3 distinct `model_ids`; sequential RUL predictions |
| POST /api/anomaly/analyze | Prediction request but anomaly task; never RUL |
| POST /api/investigate, /api/chat | `question`, optional `dataset`, `model_id`, one source, `notes`; measured evidence plus optional local reasoning |
| GET /api/knowledge/search?q= | Ranked real local project-document excerpts and stable source IDs |
| POST /api/vision/analyze | Multipart image `file`, `question`, `notes`; decoded local vision or typed unavailable |

Default dataset is FD001 on read routes. Inference requires an explicit dataset and catalog model ID; no client path is accepted. Request text is bounded. CSV/image bytes <=10,000,000, rows <=10,000, images <=16,000,000 pixels. A 65,536-byte multipart allowance exists at the request-body boundary. Exact 26-column C-MAPSS schema, finite values, one engine and contiguous ordered positive integer cycles are required for ML. Generic CSV is preview-only. Compatible-data attestation does not validate arbitrary real machines against NASA's domain.

RUL units are `operating_cycles`. `legacy_output` preserves original semantics and warnings, including padding and saved interval methods. Native model output is not silently clipped again. No calendar failure date, invented risk score or fabricated confidence is added. Historical metrics are labeled historical, not fresh evaluation.

Readiness statuses: `not_tested`, `ready` (real recorded CPU smoke passed), `unavailable`. Manifest presence alone does not establish current runtime readiness. Model integrity is checked on each worker request; missing/changed files fail closed. Request errors 422, missing IDs 404, contention 429, size 413, dependency/inference timeout 503; unexpected failures 500.

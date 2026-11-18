# ABHIGYAN — SIRE FINAL ENGINEERING MASTER DIRECTIVE
## Role: Technical Lead • Core Orchestrator • Investigation/Evidence Engine • Backend APIs • Integration and Release Owner

**Project:** SIRE — private, local-first, multimodal industrial AI investigator  
**Target:** Windows 11; Ryzen 7 7840HS; RTX 4050 Laptop GPU (~6 GB VRAM); 16 GB RAM; FastAPI/Python + React/TypeScript, CUDA-enabled local Ollama  
**Starting point:** GitHub `main` commit `34d41bc` (Phase 3 checkpoint; verify HEAD before work)  
**Showcase priority:** functional, honest, reliable local demonstration; the project showcase is planned for November 19, 2026.  
**Authority:** You own the architecture, core backend, shared contracts, integration decisions, final merge and release gate. **You have the most demanding engineering assignment.**

## 0. Operating instruction

**Implement and verify; do not merely write a plan.** Read the actual repository first. Do not assume a file named `app.py`: locate the real FastAPI application entry point (earlier reports mention `app/api/main.py`) and trace the running call graph. Read `docs/PHASE4_BACKEND_HANDOFF.md`, all Phase 3 release-readiness/results documents, existing OpenAPI, existing source ledger, test fixtures and model inventory. Preserve existing working routes; extend them with backward-compatible contracts. Coordinate API and schema changes with Kunal and model-output contracts with Cybers.

Work on your own branch `feature/final-abhigyan-core` from the verified `main` checkpoint. Never force-push, rewrite colleagues' branches, or auto-merge their work. Record file ownership and create small tested commits. Require integration approvals for shared files. **The fourth teammate owns slides, reports and synthetic sample/testing datasets; obtain fixtures and expected outcomes from them rather than rebuilding those deliverables.**

## 1. Hard protection boundaries

- Verify checksums for **813 protected inference/model files** and the **7,956 frozen stress/research results** against retained manifests. Keep original native runtime bundles and model checkpoints untouched.
- Preserve all **15 existing production tables**, their preexisting rows, attachments, evidence, saved cases and run traces. Live legitimate additions may occur; distinguish additions from unauthorized edits. Snapshot/backup before migrations. No destructive migrations.
- Keep all **12 previously checked FD001–FD004 prediction routes** and the three primary prediction pathways (LightGBM, validated ensemble, BiLSTM-attention). Do not retrain, rewrite weights or silently change preprocessing.
- Keep local-only operation, verified CUDA Ollama and bounded model residency; no mandatory cloud/API key, public hosting, unbounded downloads or research-file deletion.
- Baselines reported in earlier phases include warm text around **0.91–0.94s**, fresh multimodal investigation around **29.67s** (comparable workload), and Phase 3 short-phrase TTS around **5.67s** on the second phrase. Re-establish fresh comparable measurements before claiming improvements.
- **No fake evidence, no false model success, no made-up measurements, no invented API endpoint existing status.**

## 2. Ownership map and interfaces

**Your code ownership:** FastAPI entry/config, orchestration/runtime and model scheduler contracts, background jobs, cancellation, prediction backend, evidence/source ledger, claim verification, investigation/hypothesis engine, case-context isolation, what-if backend, case-memory service, privacy/security, persistence, API schemas, operational health, release integration. Examples of likely modules: `app/api/*`, `app/orchestration/*`, `app/investigation/*`, `app/core/*`, `app/prediction/*`, `app/knowledge/*`, evidence and run-trace services. Confirm actual paths.

**Cybers owns:** system prompts, prompt templates, generation settings, model response phrasing, structured-output tuning, answer-format evaluation and quality test corpora. Work with Cybers to define schemas; don't alter prompt policy unilaterally unless it is a safety/reliability fix.

**Kunal owns:** Figma-to-React frontend, browser voice UX, dashboards and prediction views, accessible responsive components, UI clients and frontend tests. You own server endpoints/session protocol; Kunal implements browser consumption. Do not independently redesign the UI.

**Fourth teammate owns:** PPTs, reports for presentation, sample demonstration datasets, test fixtures and presentation examples. Request content with asset IDs, timestamps, sensor units and known ground truth so engineering acceptance can be audited.

## 3. P0 — Core orchestrator and application entry point

1. Map the real entry point, middleware, dependency injection, conversation endpoint, background jobs, specialist registry, model ownership, database access and streaming events. Build a precise call graph and document only real endpoints.
2. Keep **one cognitive orchestrator**, not independent per-specialist chatbots. Route intent to fast conversation, saved-case follow-up, structured extraction, video/image, RUL inference, case retrieval, what-if, or deep investigation based on available inputs and user request.
3. Ensure greetings and trivial status questions never start expensive investigation. A greeting mentioning SIRE should not trigger a heavyweight model. General technical questions get normal LLM reasoning when required, with streaming text.
4. Speech transcript is **input provenance**, not evidence supporting claims in the answer. No stale aliases (`E1`, etc.) from an earlier turn in an evidence-free answer. Reject invalid citations only when answer evidence references are expected; do not silence ordinary greetings.
5. Maintain correct conversation/attachment association; avoid stale content in the context window, failed turns, wrong-asset evidence or incorrectly replayed voice output.
6. Keep fast-status and saved-case replies responsive while long jobs run; preserve deduplication of idempotent jobs, cancellation, retry and restart recovery. Avoid blocking Windows worker pipes, orphaned child processes, accidental lease leaks and VRAM overcommit.
7. Audit security: localhost exposure, CORS, upload validation, file path traversal, unsafe file execution, prompt injection, secret logging, privacy-safe traces and database isolation.

**Deliverable:** updated, tested orchestrator with routing-decision trace (`intent`, `selected tools`, `asset/case`, `source set`, `reason`, `latency`) and documented immutable behavior contracts.

## 4. P0 — Evidence, hypotheses and claim verification (highest priority)

SIRE's value proposition is trustworthy *engineering investigation*, not plausible prose. Fix known real-output defects:

- One synthetic multi-CSV investigation produced an incomplete mixed-language mechanism ending in `progressive degradation of潤`; no such finished mechanism may pass acceptance.
- A model previously asserted vibration data was absent even when the uploaded source contained it; source inventory and deterministic extraction must override model guesses.
- A multi-asset upload referenced `PUMP-001`, `PUMP-008`, `VALVE-003`, and later a what-if question unexpectedly resolved to `COMP-201`. Never silently change the case/asset.
- An earlier hypothesis merge sorted candidates alphabetically before truncating to eight; prevent relevant candidates being dropped solely because of lexical sorting. Evaluate ranking and retention, not just schema formatting.
- Duplicate CSV/JSON representations of one observation are one origin group, not corroboration; image-derived observations from the same image also share an origin group.
- Prior-case search formerly returned 'two provisional comparisons' without human-readable case comparisons.

Required implementation:

**4.1 Canonical evidence ledger.** Persist real source ID, type, origin group, file checksum, case ID, asset ID (or explicit unknown), captured/available timestamps, units, processing/model version, extracted location (page, cell, row, frame, timestamp), confidence/uncertainty and any source transformations. Provenance links survive document previews and API responses.

**4.2 Deterministic numerical checker.** Validate numerical values, changes, signs, units, percent deltas, time windows, and presence/absence claims against parsed source rows/cells. A model may explain evidence but cannot replace data computation. Enforce timestamp and unit normalization without silently inventing conversions.

**4.3 Asset/time/causal boundaries.** Separate observations by asset and observation time. Permit a cross-asset inference only with explicit relationship evidence and stated assumptions. C-MAPSS simulated outputs must NEVER be used to diagnose a photographed real bearing or pump.

**4.4 Hypothesis contracts.** Mechanism record must contain: concise title, plain-language mechanism, specific supporting observations with IDs, contradictions, evidence gaps, testable next checks, severity/urgency only if grounded, evidence support category, proposed vs confirmed state, ranking explanation (heuristic not probability). Reject truncated, malformed, language-drift or unsupported cause-effect prose; allow an explicit `incomplete` result instead of fabricating repairs. Keep meaningful alternatives even if >8 initial candidates; bounded relevance-based grouping and transparent omissions.

**4.5 Independent claim verifier.** Each consequential claim maps to precise evidence; invalid IDs, fabricated evidence, contradicted numbers and unstated assumptions are rejected/revised to limited statements. Distinguish model-inferred observation, deterministic calculation, simulation output, and independently verified fact. No citations required for 'Hi'.

**4.6 What-if analysis.** Resolve exact active incident, asset, intervention (e.g., 'service at hour 48'), sensor definition, baseline, modeling rule and counterfactual conditions. If ambiguous, clarify rather than default to unrelated `COMP-201`. Display *simulation* label, calculation basis and limitations; correlation is not causal effect.

**4.7 Similar prior cases.** Return actual case identifiers (redacted/local safe), source links, overlapping symptoms, differing readings, asset context, evidence strength, why they were retrieved, and whether comparison is provisional. Do not respond with only a repeated list of current hypotheses.

**Deliverable:** source-linked evidence/hypothesis contracts, deterministic verification paths, clear quality flags and regression tests on the observed failures.

## 5. P0 — Prediction engine and NASA C-MAPSS integrity

- Preserve LightGBM fast default, validated ensemble and BiLSTM-attention on-demand inference. Support FD001–FD004 and all currently advertised routes.
- Enforce exact schema, sensor names/order, unit handling, window length, operating conditions, normalization and dataset regime before calling models.
- Return RUL value with units (cycles where applicable), dataset/domain, model name/version, preprocessing ID, input validity, explanatory scope, and uncertainty/limitations. Never represent NASA simulation predictions as verified real-world failures.
- For unsupported sensor input return a structured refusal/error and needed fields; never fabricate an estimate.
- Align the prediction API with Kunal's dashboards; provide deterministic example JSON and threshold/label semantics; avoid inventing calibrated confidence if the model does not supply one.
- Check loading, cancellation and bounded GPU/CPU resource allocation while concurrent investigation runs.

## 6. P0 — Backend APIs, compatibility and handoff

Inspect existing `/openapi.json`, router files, websocket handlers and frontend calls **before** adding routes. The paths below are **candidate contracts, not claims they already exist**. Reuse existing canonical routes. Decide and sign one stable contract with Kunal and Cybers.

| Function | Proposed route/transport | Contract requirements |
|---|---|---|
| Runtime readiness | `GET /api/v1/health` | app, database, model readiness, GPU state (no secrets) |
| Specialist capabilities | `GET /api/v1/capabilities` | installed/available/partial, limits |
| Conversations | existing messages endpoint; optionally `POST /api/v1/conversations/{id}/messages` | text, attachments, mode, IDs, streamed text, evidence references |
| Uploads | existing upload/attachment endpoints | size/type checks; attachment, case, source IDs |
| Deep investigation | existing create/list/status endpoints, or `POST /api/v1/investigations` | job ID, case ID, stages, cancel/status |
| Job status/cancel | e.g. `GET /api/v1/jobs/{id}`, `POST /api/v1/jobs/{id}/cancel` | durable state and errors |
| Evidence/trace | existing `/api/v1/evidence/{id}` and `/api/v1/runs/{id}/trace` | source, offsets, provenance, tool calls |
| Cases/prior cases | existing case memory/search endpoints | comparisons, similarities, contrasts, citations |
| What-if | existing service, or `POST /api/v1/cases/{id}/what-if` | exact asset/scenario, assumptions, simulated output |
| RUL models | existing prediction inventory endpoint | FD001–FD004, models, required schema |
| RUL prediction | existing prediction endpoint, or `POST /api/v1/predictions/rul` | dataset regime, model selection, validated input, result |
| Voice streaming | jointly agreed WS/WebRTC signalling entry | session, PCM input, partial/final ASR, chunked TTS, interrupt/cancel |
| TTS/ASR fallback | existing speech endpoints | codec, sample rate, duration, errors |

Define shared JSON schemas and TypeScript types (OpenAPI generation preferred) for `ApiError`, `Case`, `Evidence`, `Hypothesis`, `PredictionResult`, `Job`, `VoiceSession` and streaming event envelopes. All events need a request/session ID, sequence number, kind, timestamp, payload and terminal/error status. Support backpressure, disconnect/reconnect and explicit cancellation. Do not break already working UI callers.

**Example P0 event types** (negotiate exact naming): `user_speech_started`, `transcript_partial`, `transcript_final`, `assistant_text_delta`, `assistant_audio_chunk`, `assistant_turn_complete`, `interrupted`, `job_progress`, `error`. Backend does NOT claim actual live browser playback; Kunal owns that acceptance.

## 7. P1 — End-to-end integration, test, and release

Create a tightly bounded acceptance matrix and run real network tests with new attachments, not only cached responses/mocks:

1. Typed greeting, typed technical question and text/voice follow-up: correct routing and valid zero-evidence behavior.
2. Image-only bearing + synthetic schematic: visible observations distinguished from mechanism inferences; correct equipment classification or explicit uncertainty.
3. PDF, XLSX, CSV: exact values, units, row/cell refs, correct duplicate source grouping.
4. Mixed assets (multiple pumps/valves): no crossed evidence or guessed root cause.
5. Conflicting documents: explicitly compare disagreements; never crash or silently pick one.
6. Vibration-present source: never say vibration is absent.
7. Multi-modal photo + PDF + CSV; video + numeric data: grounded asset/time links.
8. `service at hour 48` after a case with different asset: correct asset resolution or clarification; transparent simulation.
9. Prior-case lookup: actual cited comparison, similarities and differences.
10. All 12 FD001–FD004 model pathways; invalid inputs must fail safely.
11. Status during long investigation, duplicate requests, process/restart recovery, cancellation during GPU inference and TTS, model outage and offline mode.
12. Numerical/citation adversarial tests and source injection: no invented source IDs or unsupported statistics.

Run backend pytest, Ruff, Black, relevant Windows process tests, frontend integration smoke with Kunal, static OpenAPI/TypeScript checks and preservation audit. Capture timings clearly distinguishing cold, warm, cached, generated vs rule-based responses. Physical mic/speaker acceptance is joint with Kunal and must be marked unverified until performed.

**Release ownership:** review Cybers' quality-evaluation results and Kunal's browser QA. Merge only passing changes, document any deferred quality problems and freeze a recoverable local showcase build. No unreviewed production data change, no force push, no automated public deployment.

## 8. Integration process and deadlines

1. **First deliverable:** current API inventory/OpenAPI + file ownership map + baseline tests; send Cybers expected output schemas and Kunal API/event protocol immediately.
2. **Second:** fix hard evidence/case/citation errors in the core, using real observed failures; publish regression tests and examples.
3. **Third:** verify C-MAPSS routes, background jobs, concurrency, local-only operation and voice protocol server.
4. **Fourth:** joint integration and actual laptop showcase rehearsal; prioritize P0 over speculative model experiments.
5. **Final:** `docs/FINAL_CORE_HANDOFF.md` with branch/commit, changed files, compatibility notes, API types/examples, tests, measured results, outstanding risks, release rollback and demo instructions.

**Stop/guardrails:** do not overwrite original production data, protected model artifacts or frozen research results. If a core preservation check differs, isolate whether live legitimate additions caused it; do not erase those records. No experimental framework replacement or dangerous last-minute model upgrade.

## 9. Definition of done

Your work is accepted when the central brain reliably selects correct tools, evidence-backed investigations are asset/time consistent, generated hypotheses cannot silently pass as malformed or ungrounded, what-if and prior-case results are traceable, C-MAPSS routes are preserved, stable APIs support Kunal's frontend, Cybers' vetted outputs are integrated, real tests pass, all protected resources verify, and the local demo has a documented recovery checkpoint.

**Report real measurements and remaining gaps. No fabricated PASS. Begin the audit and implementation now.**

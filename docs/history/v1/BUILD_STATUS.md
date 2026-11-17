# SIRE application build checkpoint

2026-11-16. Repository-wide build authorized. Work is local only; no Git commit/push or public deployment.

- Preservation: external snapshot verified; see MIGRATION_LEDGER.md.
- Catalog: 44 registered routes, 790 SHA-256 records. Native binaries remain in Phase A.
- FD001 first slice: direct legacy and new wrapper both returned 115.3478990753549 operating cycles for official test engine 1, using the saved seed-42 tuned LightGBM model. This is fresh inference, not a new evaluation metric.
- API: implemented health, model catalog, assets, raw telemetry, CSV preview, RUL, compare, experimental anomaly, investigation/chat, local knowledge search and vision validation.
- Frontend: React/TypeScript/Vite/Tailwind with investigation, assets, model catalog/compare, vision, knowledge and readiness screens. Verification in progress.
- Local LLM: Ollama 0.40.16 CPU portable runtime installed and Authenticode signature Valid (Ollama Inc.). Loopback API responds, cloud disabled. Both model pulls approved and in progress. Live text/vision remain unverified until actual generation succeeds.
- All-route compatibility: 44 ready, zero failures, real CPU inference on official source engine 1 for each dataset. New application suite: 35 passed (61.98 seconds, one Starlette/AnyIO deprecation warning). Original CMAPSS suite: 56 passed (28.31 seconds). Frontend typecheck and production build passed; Vite reports a bundle-size advisory. Ruff passes. `pip check`: no broken requirements.
- No retraining, Optuna resume, recalibration, artifact rewrites or cleanup deletion.

Resume by reading this file, WORK_LOG.md, MIGRATION_LEDGER.md and STATUS.md. Current verification details live in model_store/verification.json. Do not treat historical tests as current checks.

## Remaining verification and current installation

Live HTTP checks returned 200 for `/`, health, models and assets. FD003 engine 1 via the real HTTP API returned 43.38973340387454 operating cycles. All 790 inference file hashes match the external pre-build snapshot.

Browser/mobile QA is incomplete: in-app browser host unavailable; native Windows computer use stopped because it could not establish the browser URL safely. No browser-based interactions or screenshots are claimed.

User approved Ollama and both configured models. The official full installer download stalled at a low transfer rate. A smaller CPU-only portable runtime is being installed from the official release ZIP with per-entry CRC verification. Original signed executable authenticity will be checked before execution. No completed local LLM inference is claimed yet.

Preservation audit: all 4,100 original Phase A working files still match their snapshot hashes. New-source secret-pattern scan: zero matches. API OpenAPI currently has 12 implemented paths.

Live local text smoke: `python scripts/smoke_test.py` returned `INVESTIGATION ready`. Qwen3 4B produced valid schema with references to supplied evidence IDs. Saved measured evidence and generated interpretations are separate in docs/SMOKE_RESULTS.json. This confirms connectivity/schema behavior, not clinical or engineering diagnostic accuracy; small-model interpretations still need review.

Vision retry evidence: full app request failed closed again after a longer generated response; the small default tag resolves to the thinking variant. A separate short direct image probe returned valid JSON and identified a bearing, confirming the image pipeline/runtime works. The explicit 2B instruct tag is being pulled as the configured application variant; the original downloaded default variant remains preserved. Full API vision readiness is not yet claimed.

## Final local checkpoint

| Check | Actual result |
| --- | --- |
| Registered model routes | 44 CPU successes, zero failures |
| Original Phase A file preservation | 4,100 checked, zero differences |
| Inference dependency hashes | 790 match the pre-build snapshot |
| New application tests | 35 passed; one Starlette/AnyIO deprecation warning |
| Existing CMAPSS tests | 56 passed |
| Provider tests after context change | 4 passed |
| TypeScript and Vite production build | Pass; bundle-size advisory |
| Ruff / Black / pip dependency check | Pass |
| Clean launcher startup | API + Ollama started; ML/text/vision availability true |
| Real text investigation | Structured local Qwen response with actual evidence references |
| Real vision HTTP request | 200 with qwen3-vl:2b-instruct; 45 seconds CPU |
| Browser/mobile visual checks | Blocked by unavailable browser host / Windows URL detection |

The final vision response and prior failed attempts are in SMOKE_RESULTS.json; model digests in OLLAMA_MODELS.json. An ad-hoc metadata recorder raised a Response context-manager TypeError after saving the successful vision response; the metadata snapshot was subsequently corrected without rerunning or inventing inference. The request itself returned HTTP 200.

Generative quality remains limited: these are small local models. Their interpretations are labeled unverified, and a cited source ID does not prove every generated sentence is entailed. This is not a validated fault-diagnosis classifier. No accuracy benchmark for vision/text was performed.

Current scope exceptions: the app exposes 44 registered routes, not every unregistered baseline/seed/RUL-autoencoder variant. Those files remain unchanged. N-CMAPSS, persistent cases, maintenance-manual ingestion, hosted providers, public deployment, mobile camera verification and retiring old research directories remain unimplemented or unverified. No irreversible cleanup is proposed.

The private runtime bundle and checksum metadata are generated by `python scripts/package_demo.py` under ignored output/. It includes original inference bytes and NASA demo histories, but excludes Python environments, Node modules and Ollama weights. It is not a public release or a fully self-installing offline environment.

Start: `.\scripts\dev.ps1`. Local URL: http://127.0.0.1:8000 ; API docs: http://127.0.0.1:8000/docs . QA services are stopped at session teardown; the launcher restarts both.

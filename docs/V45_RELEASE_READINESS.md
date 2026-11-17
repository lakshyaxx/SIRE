> Current conversation patch is V4.5.1: [real-user regression findings](CONVERSATION_REGRESSION_FINDINGS.md). The V4.5 baseline measurements below are historical; wider acceptance gaps remain open.

# V4.5 release readiness — engineering preview

V4.5 is running locally at **http://127.0.0.1:8000**. It is not fully accepted against the complete directive: natural voice speed/device acceptance and general semantic hypothesis quality remain open. No paid service, retraining, public deployment, protected cleanup or evaluator access occurred.

## Verified release gates

| Gate | Actual result |
|---|---|
| Backend regression |275passed,2dependency warnings,164.84s; final small voice-schema event-list correction separately1passed/2.03s|
| Static checks |Ruff passes; Black passes; TypeScript passes|
| Frontend tests |10passed,0failed,1376.9247ms|
| Build |645modules,18.74s;799347byte JS; existing bundle-size warning|
| Main loaded identity |API4.5.0; source/frontend fingerprint `86e3151959b98874ca5efee79197d264639424ce7b612be1d3e0cd1a1f6d2096`; actual served JS/CSS bytes verified|
| Main model readiness |Native startup probe passes; text/vision/Ollama ready;179provider descriptors|
| REST handoff |58paths,24schemas,0unresolved local OpenAPI refs|
| Frontend API-client smoke |7targeted checks pass; real5file uploads and completed generated-photo/PDF/CSV case; detailed semantic gaps below|
| Loopback integration |17actual checks pass, including12genuine selected native routes, semantic numeric negatives, video, WebSocket VAD/ASR/chat/TTS and real heavy-job cancellation|
| Offline/failure |5isolated-process DNS/connect-guard checks pass; source-backed retrieval survives actual provider connection refusal|
| Preservation |813native files,7956frozen results,13old production tables and3original bundles unchanged;168routes retained; only additive `v45_jobs` table at main startup|

Earlier failures and corrections are retained, not replaced with fabricated passes: initial harness image-hash assumption;70.823s status route; first full suite272pass/1fail on Windows input-pipe cancellation; incomplete free-text citation expansion; one missing test import. The last full suite and relevant focused reruns pass. Warnings are existing Starlette/AnyIO deprecation and Joblib logical-core fallback on this Windows host.

## Delivered behavior

Durable bounded background investigation, same-conversation deterministic status/recall, preserved candidate/deferred registry, immutable source inventory with absence correction, asset/time/number safeguards, unified actual provider discovery, process-cooperating resource queue, cancellable structured/vision/native work, genuine VAD/final-ASR voice session, inline speech prefetch, three native prediction roles and concise report/full JSON exports. No visual redesign.

Final actual generated-photo case `6e738cbc7a07480bb9403ec74e5380c8`:2tentative low-support alternatives, no measured falsification, explicit unlinked sensor support, one false absence claim contradicted by250good source rows. This demonstrates guardrails; it is not a validated diagnosis. The final report is9pages/19147bytes; all18evidence snapshots and2750measurement rows remain in its JSON audit. Every page was rendered in a contact sheet and the first page reviewed at readable scale; long opaque source IDs remain visually dense but no clipping/overlap was observed.

## Open acceptance items and minimal remediation order

1. **High: voice speed and physical browser acceptance.** Actual file/network cycle75.406s;2–5s spoken aspiration not met. Browser host unavailable prevented direct microphone/speaker/autoplay/barge-in acceptance. Manually test Start, question, inline playback, interruption, follow-up and Stop; never auto-grant privacy permissions. Then profile initialization/prefill/decode and test bounded residency or a compatible isolated faster speech path using actual recordings.
2. **High: semantic hypothesis quality.** The small model sometimes emits incomplete mechanism descriptions and unsupported proposed relationships. Numeric/absence checks do not establish general entailment. Preserve original outputs, shorten/validate complete mechanism names, and evaluate claims on approved independently labeled evidence. Do not report top-1/top-3/FPR without an isolated legitimate evaluator.
3. **Medium: warm/cold resource profiling.** Resident warm LLM, per-model RSS/VRAM, CPU utilization, physical audible timing, Hindi/noisy-ASR accuracy and clean-environment portability remain unmeasured. Current final ordinary first text10.093s; first meaningful background source facts1.433s. System sampled RAM peak14026.957MiB/GPU311MiB are whole-system observations, not exclusive SIRE costs.
4. **Medium: optional specialists.** Qwen ASR/TTS adapters/large downloads remain deferred because dependencies are absent and upstream pins differ. No fake adapter, benchmark or multilingual claim. Continuous video-motion reasoning is not implemented.
5. **Lower: packaging/frontend size.** Root `.venv` still depends on the preserved external environment; JS bundle-size warning remains. Split/bundle and clean-install validation should follow correctness/performance work, preserving the working local app and weights.

OS-wide disconnected networking was not tested; the isolated Python guard blocks external connect/DNS for that process/children while allowing actual local Ollama. Existing Ollama egress is outside that guard. Existing local service settings and installed tags were preserved; no hosted AI fallback exists in these exercised paths.

## Launch, review and evidence

From root: `.\.venv\Scripts\python.exe scripts/dev.py`. Health `/api/v1/health`; docs `/docs`. The launcher reuses existing Ollama and only owns services it starts. The previously running shared Ollama PID29972/start17Nov15:07:55 remained unchanged through main cutover. Main is loopback-only. QA8001 was stopped after acceptance; all synthetic records remain in V45 disposable namespaces.

See [API handoff](V45_FRONTEND_API_HANDOFF.md), [architecture](V45_ARCHITECTURE.md), [capabilities](V45_CAPABILITY_MATRIX.md), [measured performance](V45_PERFORMANCE_RESULTS.md), [evidence](V45_EVIDENCE_VERIFICATION.md), [hypotheses](V45_HYPOTHESIS_ENGINE.md), [registry](V45_MODEL_REGISTRY.md), [archive decision](V45_ARCHIVE_MANIFEST.md) and [progress](V45_PROGRESS.md).

Actual proof paths: `.runtime/v45/full_regression_final.log`, `client_photo_final/verification.json`, `network_acceptance/results.json`, `offline_acceptance/results.json`, `performance_results_inprocess.json`, `startup_benchmark/results.json`, `main_contract.json`, `preservation_after_cutover.json`, `archive_dependency_audit.json`, `reports/final/`. Failed attempts remain alongside them. No new comprehensive stress campaign or ground-truth accuracy result is claimed.

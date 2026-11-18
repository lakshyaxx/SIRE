# Phase 3 release readiness

**Verified local engineering release: SIRE 4.7.0, running at http://127.0.0.1:8000.** Implementation, regressions, real network controls and preservation checks pass. **Full acceptance is conditional:** independent multimodal/causal quality review and physical voice/browser acceptance remain unverified. This is not an unqualified claim that every Phase 3 definition-of-complete requirement is proven.

Loaded source SHA-256 `da2589035d0c4b4261a1e2d13b6eb15d9a01e39a62efc80f708c9d91a3f55252` matches disk; served HTML/JS/CSS match the built files; text, vision, Ollama and native readiness are true. Contract2.0/specialists1.0 remain stable, OpenAPI missing references zero. Immediate cutover comparison passes all 15 production tables exactly. Earlier legitimate live additions are preserved and documented.

| Check | Actual result |
| --- | --- |
| Backend pytest | 334 passed / 1 warning / 147.73s |
| Frontend node tests | 13 passed / 0 failed / 845.3593ms |
| TypeScript + Vite | 646 modules / 9.65s; passed |
| Ruff | All checks passed |
| Black | 202 files would be left unchanged |
| pip check | No broken requirements found. |
| Paired actual HTTP | 24/24 before + 24/24 after |
| Actual reliability groups | 6/6 passed |
| Guarded offline checks | 7/7 passed |
| Actual restart | interrupted / process_restarted |
| Main read-only cutover | 4.7.0 source/frontend ready / 15 exact tables / no missing OpenAPI refs |

## Delivered

Bounded resident CPU speech/embedding workers with actual initialization reuse; one engine per media worker ; 90s idle eviction; source/model integrity; owned-child cancellation and parent-exit cleanup; explicit real same-model one-shot fallback. Existing central scheduler/one GPU model preserved. Native registry paths corrected. Saved context routing and audio chunk/document parsing defects fixed. Exact cache-hit metadata corrected. Hypothesis ties, channel-absence contradictions and incomplete prose receive explicit checks; saved history is reviewed without rewriting it. No extra planning/repair model calls.

Fresh 26-character speech 12.180→5.667s, fresh 218-character speech 33.830→27.358s; repeat semantic query 1.697→0.325s. Warm text 0.939→0.914s. These are descriptive single paired observations, with shared live workload; vision's queue-confounded gain is not attributed to optimization. [All timings](PHASE3_BENCHMARK_RESULTS.md).

GPU text 3.2 GB / vision 2.0 GB 100% offload observed; original 51 runtime files preserved. All 813 native files, 7,956 frozen files, 3 original bundles, 13 media/embedding assets, 20 Ollama blobs and original production rows preserved. No downloads, retraining, cleanup, push or public deployment. Local rollback checkpoint `a635f1055c571e0d5a5bec12afc6439f3be2905c`; don't use destructive reset/revert over user changes. CPU resident flags can be disabled in media/retrieval YAML for the original one-shot path, followed by verified restart; no DB restore is required or appropriate. Keep source fingerprints/cache generations consistent.

## Acceptance gaps and priorities

| Priority | Remaining work | Evidence / consequence |
| --- | --- | --- |
| P1 | Independent semantic/causal and multimodal no-regression review | Real integration passes; broad diagnostic accuracy was not measured |
| P1 | Physical browser/mic/speaker/echo/interruption acceptance | Network WAV/PCM and frontend unit checks cannot establish audible/device behavior |
| P1 | Cold/long new speech latency | Neural generation remains slow; reuse removes setup, not kernel cost |
| P1 | Generated mechanism completeness | Final model still emits a fragment; now flagged instead of falsely accepted |
| P2 | Broader technical/noisy speech and blind listening | Tiny public synthetic cohort only; WER unchanged on paired recording |
| P2 | Portable fresh-environment, sustained memory/thermal/OOM qualification | This Windows environment tested; preserved external dependencies remain |
| P2 | Existing Vite size / AnyIO warning | Not introduced by this release; no UI rewrite attempted |

Safe release verification is complete within these stated limits. Do not call the full industrial/continuous-voice product accepted. Phase 4 integration instructions: [handoff](PHASE4_BACKEND_HANDOFF.md). Complete source-backed result record: [PHASE3_RESULTS.json](PHASE3_RESULTS.json).

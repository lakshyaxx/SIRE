# Phase 3 benchmark results

Actual paired loopback HTTP workload: 24 operations before and 24 after, all passed. Private raw answers, plans, tool traces, input hashes, WAV files and timestamps remain in `.runtime/phase3_20261118/before/` and `after_final/`. Receipt SHA-256 values and conditions are in [PHASE3_RESULTS.json](PHASE3_RESULTS.json). No ground-truth cause labels or evaluator-only files were accessed.

One observation per condition on the same laptop; no confidence intervals or statistical performance claim. Live production and QA shared Ollama. Baseline vision waited 11.593 seconds in the queue, so its apparent gain is confounded. Native CUDA/OS file caches were not forcibly cleared. Harness totals include response handling, trace reads and audio decoding/writing; provider phase timings are separate. After TTS follows ASR: its first call is model-cold/process-warm, subsequent distinct exact texts are model-warm and uncached. ASR specialist reads are cached ingestion results, not fresh recognition.

| Operation | Before s | After s | Interpretation |
| --- | --- | --- | --- |
| text_cold | 5.803 | 5.305 | Single paired observation |
| text_warm | 0.939 | 0.914 | Single paired observation |
| greeting | 0.076 | 0.079 | Single paired observation |
| capabilities | 0.102 | 0.108 | Single paired observation |
| pdf | 0.263 | 0.226 | Single paired observation |
| csv | 0.573 | 0.478 | Single paired observation |
| xlsx | 2.879 | 2.503 | Single paired observation |
| docx | 0.590 | 0.587 | Single paired observation |
| retrieval_first | 2.322 | 2.157 | Single paired observation |
| retrieval_repeat | 1.697 | 0.325 | Single paired observation |
| asr_short | 0.170 | 0.113 | Saved extraction read; fresh ASR measured during upload |
| asr_technical_base | 0.123 | 0.122 | Saved extraction read; fresh ASR measured during upload |
| asr_technical_tiny | 0.130 | 0.103 | Saved extraction read; fresh ASR measured during upload |
| tts_0 | 12.418 | 9.274 | Fresh model-cold TTS / reused process |
| tts_1 | 12.180 | 5.667 | Fresh exact text / warm TTS model |
| tts_2 | 17.635 | 10.957 | Fresh exact text / warm TTS model |
| tts_3 | 33.830 | 27.358 | Fresh exact text / warm TTS model |
| image | 21.852 | 9.653 | Queue-confounded; no VLM optimization claim |
| vision_to_text | 6.817 | 6.416 | Single paired observation |
| video | 18.028 | 16.873 | Single paired observation |
| rul_low_latency | 5.959 | 5.937 | Single paired observation |
| rul_advanced | 13.978 | 13.072 | Single paired observation |
| rul_deep | 9.607 | 9.488 | Single paired observation |
| deep | 23.838 | 22.822 | Single paired observation |

## Current-source acceptance after all fixes

| Request | First displayed text s | Total s | Route |
| --- | --- | --- | --- |
| first_general | 5.666 | 5.668 | evidence_conversation |
| repeat_general | 0.918 | 0.919 | evidence_conversation |
| greeting | 0.067 | 0.068 | fast_conversation |

Fresh current-source multimodal investigation: **29.565 seconds**, compared with the earlier optimized paired run 22.822 seconds. This observed variability is retained; there is no guaranteed deep-investigation latency. Both complete with real generated-image observations, document/table evidence and strict reference identities. Broad causal correctness was not scored. One incomplete generated mechanism is correctly flagged by the final code.

Current first general request observed no initial Ollama residency. The cold load dominates; warm first model token precedes first displayed text because engineering commentary waits for validation. Exact Ollama load/prefill/generation counters are in the machine-readable final_text records. Greetings use no model.

## Preserved genuine native inference

| Route | Model | Before cycles | After cycles | Exact equality |
| --- | --- | --- | --- | --- |
| rul_low_latency | fd001-01_lightgbm-s42 | 115.3478990753549 | 115.3478990753549 | True |
| rul_advanced | fd001-08_ensemble-s42 | 114.0469882715471 | 114.0469882715471 | True |
| rul_deep | fd001-03_bilstm_attention-s42 | 121.52069061994553 | 121.52069061994553 | True |

These three fresh primary FD001 calls use genuine compatible saved NASA history, never synthetic oil-rig telemetry. They do not requalify every historical model/dataset combination. All 813 inference files are hash-verified; prior Phase 2 integration evidence and frozen stress results are preserved.

See [voice details](PHASE3_VOICE_PERFORMANCE.md), [reliability/tests](PHASE3_TEST_REPORT.md), and [diagnosis](PHASE3_PERFORMANCE_DIAGNOSIS.md).

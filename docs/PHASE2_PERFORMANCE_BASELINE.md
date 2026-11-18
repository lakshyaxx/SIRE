# Phase 2 measured performance baseline

Historical Phase1 reference: general text6.187s cold/0.938s warm, deep29.672s, unseen220character Kokoro32.047s. These came from the earlier actual report, not estimates. Current workloads are small samples, not statistically established speedups. Different prompts/lengths cannot be compared as identical work. Browser rendering, first audible output, physical microphone and OS-wide cold caches were not measured.

| Final serial local general question | Checked first text | Full response |
|---|---:|---:|
| Explicitly unloaded model residency | 5.498s | 5.500s |
| Resident follow-up | 0.998s | 0.999s |

The same general question as Phase1 was used. History differs on the warm turn. No concurrent suite during this final profile. Source-reference validation completes before model commentary is exposed, so checked first text differs from the raw first model token.

| State | Prompt tokens | Cached prefix | Load | Prefill | Generated tokens / time | Tokens/s | Raw first token |
|---|---:|---:|---:|---:|---|---:|---:|
| residency_cold | 294 | 0 | 4.285923s | 0.297555s | 39 / 0.699587s | 55.747 | 4.656s |
| resident_warm | 368 | 167 | 0.006466s | 0.077682s | 39 / 0.694777s | 56.133 | 0.172s |

| Compound job | Actual complete time | Same-case greeting while heavy active |
|---|---:|---:|
| Photo + PDF + CSV + equivalent JSON | 29.863s | 0.090s |
| Video + original sensor data | 38.186s | 0.074s |

| Speech / retrieval | First usable completed output | Total |
|---|---:|---:|
| New two-sentence Kokoro request | 11.765s | 21.752s |
| Exact same WAVs replayed from bounded cache | 0.232s | 0.420s |
| MiniLM first case query | Not separately measured | 1.369s |
| MiniLM repeat query (zero new chunk vectors) | Not separately measured | 1.348s |

Actual speech text: “Independent inspection is required. Record the measured pressure.” This is completed-sentence streaming, not a faster neural engine or partial audio waveform. Cache only accelerates identical prior successful audio. Native final-utterance Silero→Whisper WebSocket replay: 7.334s. Network default base ASR 5.322s; explicit tiny fallback 4.379s.

| Stage C modality / pathway | Full API call | Qualification |
|---|---:|---|
| 01_greeting_no_model | 7.547s | FAILED first attempt; fixed actual rerun |
| 02_documented_capabilities_no_model | 0.100s | Actual functional call |
| 03_image_only | 11.108s | Actual functional call |
| 04_pdf_extraction | 0.312s | Actual functional call |
| 05_csv_statistics | 0.627s | Actual functional call |
| 06_xlsx_interpretation | 3.085s | Actual functional call |
| 07_short_speech | 5.387s | Actual functional call |
| 08_industrial_speech | 6.407s | Actual functional call |
| 09_new_configured_voice_synthesis | 18.325s | Actual functional call |
| 10_sampled_video | 23.373s | Actual functional call |
| 16_native_all_primary_saved_pathways | 107.058s | Actual functional call |

StageC and compound timings precede the final source-selection/output-budget fix and establish functional execution; they are not a final-code statistical performance comparison. Some brief targeted tests overlapped StageC video. All12 native primary routes used genuine saved histories; the aggregate is not a single-prediction latency. Actual final clean schematic 3.118s. Final post-fix contradictory handover+sensor conversation 17.568s. Active GPU cancellation acknowledgement-to-terminal 0.045s. Workload-specific cold/warm model startup is only separated when provider counters record it; other values remain unmeasured, not inferred.

Observed resources: retained worker OS lifetime CPU time and peak resident memory are exported under `worker_resource_observations` in [validation summary](PHASE2_VALIDATION_SUMMARY.json). Actual fresh TTS workers include453492736B and434110464B peakRSS, CPU21.78125s/17.75s; multiple synthesis threads make lifetime CPU time exceed elapsed time. Worker imports/model startup are included. No system-wide peak or instantaneous CPU utilization claim. Model-specific Qwen VRAM is from `/api/ps`, total GPU memory includes desktop/other workloads. Current direct eight-token smoke is **4.084s**,100%GPU/3.2GB/4096context; it is not substituted for the general-question benchmark.

Remaining Phase3 bottlenecks: slow fresh Kokoro inference/initialization, per-query embedding-worker startup, switching VLM/text residency on6GB, small conceptual relevance evaluation and occasional ASR errors. No evidence of mandatory cloud/CPU Qwen fallback in these accepted GPU tests. Do not promise a cold driver/cache installation matches warmed CUDA timings.

# Phase 3 performance diagnosis

The largest confirmed avoidable cost was loading CPU speech/embedding packages and weights for every call. Bounded reuse removes repeated initialization. Short fresh TTS 12.180 → 5.667 seconds and repeat semantic retrieval 1.697 → 0.325 seconds. Warm text was already GPU-fast: 0.939 → 0.914 seconds; no major text-generation acceleration claim.

## Actual current Qwen phase timings

| Condition | Load s | Prompt tokens | Prefill s | Generated tokens | Tokens/s | Provider first token s | First displayed text s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| first_general | 4.547 | 294 | 0.263 | 39 | 58.12 | 4.891 | 5.666 |
| repeat_general | 0.008 | 368 | 0.067 | 39 | 60.33 | 0.156 | 0.918 |

All counters come from actual Ollama responses; tokens/s is generated tokens divided by reported eval duration. First-token seconds includes provider-side queue/load handling, unlike raw prefill alone. Engineering model commentary is intentionally buffered until source checks finish. Fast social/capability/saved-context routes avoid the LLM. No fabricated citations or global validation bypass was added.

## Confirmed bottlenecks and repairs

| Finding | Evidence and change | Remaining limit |
| --- | --- | --- |
| Repeated Kokoro/Whisper setup | Same model retained for fresh requests; measured warm initialization zero | CPU neural generation remains slow, profile switches reload |
| Repeated MiniLM imports/session | Retain tokenizer and ONNX session; actual new query inference | First query still pays cold setup; vectors remain derived |
| Incorrect model registry paths | Resolve native artifact paths against preserved C-MAPSS root | Availability is not diagnostic accuracy |
| Saved-history route misses | Natural singular/plural recall now reads saved records without LLM | Explicit fresh analysis still invokes real tools |
| Audio chunks reparsed as documents | Restrict document search to actual document/CSV attachment kinds | Audio remains unverified input provenance |
| Native startup stall | Preload native packages before reader thread | Underlying DLL-lock mechanism unproven |
| Owned Python launcher differs from interpreter | Cancel only owned PID tree; actual child-handle test | Platform behavior tested on this Windows system |
| Stale cache execution metadata | Exact prior WAV now declares no inference/worker | Cached replay is not a fresh speech benchmark |

No extra planning/repair LLM calls, speculative preloads, model downloads, new architecture, GPU runtime replacements or global parallelism increase. Existing 4096 context, one loaded Ollama model, one heavy slot and 120-second GPU keepalive remain bounded. CPU workers add retained memory until 90-second idle eviction; reported peak RSS is process-lifetime, not whole-system or per-request peak. Resource fields that were not measured remain unknown.

Image before/after is queue-confounded; no VLM speedup claim. Deep latency varies (paired after 22.822s; latest 29.565s). Cold starts, long new TTS and model-dependent requests behind a running heavy call remain the main practical delays. [Complete benchmark](PHASE3_BENCHMARK_RESULTS.md).

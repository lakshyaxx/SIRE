# SIRE performance diagnosis — 2026-11-18

Final normal-runtime measurements: general question **6.187 seconds cold / 0.938 seconds warm**, fresh multimodal investigation **29.672 seconds**. New speech synthesis remains slow. Detailed staged, cold, warm and first-use measurements follow.

## Files and commands

Added `scripts/profile_sire_performance.py`, `app/media/cache.py`, `tests/unit/test_performance_cache.py`, this report and `PERFORMANCE_RESULTS.json`. Updated the Ollama adapters/registry, media runtime/worker, speech response headers, app version, `config/app.yaml`, `config/media.yaml`, `V45_PROGRESS.md` and root `STATUS.md`. The additive CUDA directory and its manifest are outside the repository in the existing per-user runtime; no model files were downloaded.

Commands run: `.venv/Scripts/python.exe -m pytest -q` → **293 passed, 1 warning in 145.21 seconds**; `npm test` → **13 passed**; `npm run build` → TypeScript and Vite passed, **646 modules / 10.17 seconds**; Ruff passed; Black checked **75 files**. Local profiling commands, actual answers, provider counters, source IDs and retained trace locations are recorded below and in the JSON report.

SIRE 4.5.2 is running locally at http://127.0.0.1:8000. Normal Ollama now uses the RTX 4050. This was a CPU-only portable installation despite a working NVIDIA driver and CUDA-capable PyTorch. No new models, training, architecture migration or public deployment occurred. Existing citation validation and engineering evidence checks remain enabled.

## Evidence and scope

Actual serial HTTP/SSE requests, real Ollama counters, `nvidia-smi`, `ollama ps`, actual file ASR/Kokoro WAV output and fresh image/PDF/CSV investigations. Disposable QA databases only; no synthetic production messages. Small samples, output lengths differ, OS caches not flushed. Timings describe local transport and processing; browser rendering, microphone capture, audible playback and physical interruption were not measured. Performance does not establish diagnostic accuracy.

Machine-readable measurements and raw proof locations: [PERFORMANCE_RESULTS.json](PERFORMANCE_RESULTS.json). Raw files stay private under `.runtime/performance_20261118/`. Failed initial GPU readiness probe, expensive first-use runs and first preservation comparison are retained.

## Confirmed causes and fixes

1. **CPU-only Ollama runtime.** Its original `sire-install-manifest.json` explicitly omitted GPU extras. `/api/ps` reported `size_vram=0`; original CLI reported CPU. NVIDIA RTX4050 Laptop has6141MiB, driver621.01; existing Torch2.8.0+cu128 reports CUDA available. Added18 same-version official CUDA13 runtime DLLs. All33 original runtime files retain their SHA256 hashes. Exact configured models remain Q4_K_M, tags/digests unchanged. GPU logs show text37/37 layers and vision29/29 layers offloaded, with CLIP using CUDA. Actual normal-runtime text CLI reports100%GPU and3180247121bytes model VRAM. Whole GPU memory also includes the desktop and is not an exclusive model allocation.
2. **Immediate unloading between turns.** Chat and structured/vision requests used `keep_alive=0`, reloading for repeat questions. Now120seconds, still one loaded model and one cooperating heavy operation. Vision-to-text replacement still occurs on this6GB device. No speculative extra model loads added.
3. **Repeated HTTP trust-context initialization and event-loop blocking.** Actual client construction took0.412–0.516s in three probes; reusing the default verified context took0.000196–0.000305s. HTTPX built a trust context even for HTTP. A single verified context is reused; certificate/hostname validation remains enabled. Synchronous model discovery in `stream` now runs off the async event loop. Tests verify both properties.
4. **CPU speech synthesis.** Genuine51-character Kokoro cProfile probes:1thread14.453s,2threads15.094s,4threads13.734s. Four threads chosen; ASR remains2threads. Most time was native generation plus model initialization. New220-character speech still took32.047s in the full after-run. Added an8-entry/8000000-byte/300second in-memory cache of successful actual WAVs, bound to exact text, pinned weights, thread policy and synthesis/normalization source. Full model integrity checks and cancellation precede reuse. Hits are explicitly marked by `X-Speech-Cache`; identical WAV SHA verified. Cache helps repeated playback, not unseen speech. No persistent speech-worker architecture was introduced.

## Measured before/after

| Workload | Original CPU | Staged GPU after initialization |
|---|---:|---:|
| Direct text, residency cold |10.813s|5.843s|
| Direct same-prompt resident warm |3.515s|0.782s|
| App general question, cold |13.047s|6.969s|
| App general question, repeat |14.031s|2.000s|
| Actual file ASR → chat → complete WAV |52.297s|38.563s|
| Fresh multimodal investigation |138.031s|30.532s|

The table predates the final HTTP-context optimization. Restarted final normal-runtime general-question totals are **6.187s cold and0.938s warm**, checked first-text **6.172s/0.938s**. Final social/capability requests took0.078s/0.094s without model calls. Final normal-runtime fresh deep case completed **29.672s**, with actual trace retained; this includes both configured GPU model families.

Direct model counters (same47-token prompt, deterministic seed42, temperature0,4096context; generation token counts differ):

| Phase | CPU cold | GPU cold | CPU warm | GPU warm |
|---|---:|---:|---:|---:|
| Model load |5.648s|4.782s|0.022s|0.013s|
| Prompt evaluation |0.797s|0.258s|0.093s|0.019s|
| Generation |3.740s/37tokens|0.682s/35tokens|3.265s/37tokens|0.644s/37tokens|
| Generation tokens/s |9.893|51.291|11.331|57.461|
| First model token |6.469s|5.046s|0.156s|0.047s|

Warm requests reused46 of47 prompt tokens, so these warm prefill numbers are prefix-cache timings, not a full47-token throughput comparison. App checked first text is later than raw model first token because validation completes before releasing model commentary. The validator was retained.

First-ever CUDA direct request took123.328s: provider load66.569s/prefill52.026s. First GPU deep run106.078s included84.266s vision; vision load23.488s/prefill55.161s. These are recorded first-use startup costs. Subsequent uncached vision requests10.657s and4.687s; fresh repeat full investigation30.532s used vision10.625s/hypotheses17.875s. Precise compilation-versus-driver initialization attribution is not proven. Do not use these warm results as a guarantee for a fresh driver/cache installation.

Voice before/after: ASR intake4.641/4.531s, chat12.281/1.969s, new WAV35.359/32.047s. Same previously synthesized WAV replay0.171/0.172s with exact matching SHA. First-audible latency remains null. The actual public file transcript was imperfect and was passed unchanged, not replaced with an expected question.

General traces show one `llm.chat`, no investigation tools and294 initial prompt tokens within4096context. Deep traces show one vision call and one hypothesis proposal,2315 proposal input tokens; no repeated proposal loop found in these cases. Measured scheduler queue was0–0.016s in the staged after-run. No contention bottleneck was demonstrated under these serial samples. One-heavy-operation scheduling can still queue concurrent work; concurrency performance was not claimed tested.

## Verification and preservation

Backend **293 passed/1 warning/145.21s** after the final transport patch; frontend13passed/938.7942ms, TypeScript passes,646-module Vite build10.17s. Ruff passes; Black75files unchanged. Existing801.51kB JS chunk advisory and Starlette deprecation warning remain. New regression tests cover cache bounds/expiry/metadata isolation, invalid model hashes/Stop, verified trust context and nonblocking discovery. Native cancellation/registry regressions also pass.

Read-only preservation:813 native artifact hashes,7956 frozen result hashes/sizes,20 Ollama content-addressed blob hashes and3 original bundle hashes verified. Every15 production table exactly matches the immediate pre-cutover backup. Compared with task-start backup, one already-existing voice session changed listening→error before cutover and gained its received-PCM checksum; all original turns and all original metadata remain identical. The first stricter comparison flagged this and is retained rather than called an exact pass. No test messages or attachments entered production.

An old4.5.1 process returned500 on the pre-restart resource endpoint after lazily importing updated code against its old in-memory configuration. The restarted process passes health/resources and loaded-source/frontend identity checks. This intermediate failure and restart boundary are recorded; running source edits were not treated as loaded production changes.

## Runtime provenance, rollback and reproduction

CUDA members came from the [official0.40.16 Windows release](https://github.com/ollama/ollama/releases/tag/v0.40.16). Only selected CUDA ZIP members were downloaded, with exact size/CRC, per-file SHA256 and valid Ollama/Microsoft Authenticode signatures. The entire remote ZIP SHA was not verified; its published reference digest is recorded separately. This is a runtime addition, not a model download. [Official Windows runtime documentation](https://raw.githubusercontent.com/ollama/ollama/v0.40.16/docs/windows.mdx) describes the standalone NVIDIA libraries; [official GPU documentation](https://raw.githubusercontent.com/ollama/ollama/v0.40.16/docs/gpu.mdx) covers supported devices/drivers.

Normal launcher remains `scripts/dev.ps1`, with local-only8000/11434 services, one loaded model, no cloud. To roll back CUDA, stop the verified SIRE Ollama process, move only additive `lib/ollama/cuda_v13` outside its runtime, and restart; preserve all original CPU files. Source/DB checkpoints and exact runtime additive manifest are private under `.runtime/performance_20261118/` and `SIRE-Ollama/sire-cuda-addon-manifest.json`. Do not restore a production DB over later user work.

Reproduce in a fresh disposable state, never production:

```powershell
$env:SIRE_STATE_DIR=(Join-Path (Get-Location) '.runtime/performance_20261118/new_qa_state')
$env:OLLAMA_BASE_URL='http://127.0.0.1:11434'
.\.venv\Scripts\python.exe -m uvicorn app.api.main:create_app --factory --host 127.0.0.1 --port 8001 --ws wsproto
# Separate terminal; supply the public corpus root, never evaluator_only:
.\.venv\Scripts\python.exe scripts/profile_sire_performance.py --corpus <PUBLIC_CORPUS_ROOT> --output .runtime/performance_20261118/new_run
.\.venv\Scripts\python.exe -m pytest -q
```

The public app factory honors `SIRE_STATE_DIR`; its normal native startup probe uses the unchanged saved model. Use a fresh output directory. Run one benchmark at a time with no concurrent test suite; its explicit unload probes are disruptive to other local requests. `--direct-only` and `--deep-only` provide bounded subsets.

Remaining priorities: new-utterance CPU TTS latency; physical browser/microphone/speaker timing and interruption acceptance; larger controlled latency samples. Current semantic diagnosis limitations from V4.5 remain open. No redesign or additional models were used to substitute for these gaps.

# V4.5 measured results

All timings below come from executed code, not estimates. Single-run results are indicative; no load-capacity or p95 claim. Backend regression and some engineering IO ran during initial network acceptance; those results include that contention. Physical browser/audio timing is unavailable because the browser automation host was unavailable.

## Comparable in-process text probe

Same question/helper shape, actual Qwen, no resident Ollama model before either probe. Final proof: `.runtime/v45/performance_results_inprocess.json`.

| Measure | V4 baseline | V4.5 |
|---|---:|---:|
| First actual event |0.047s|0.047s|
| First actual text |10.938s|11.016s|
| Complete |13.578s|13.344s|
| Peak sampled system RAM |15313.730MiB|14026.957MiB|
| Peak sampled desktop GPU memory |348MiB|311MiB|

There is no demonstrated meaningful text-generation speedup. Lower sampled whole-system RAM cannot be attributed to SIRE changes because other application usage differs. Samples are every2seconds; they are not exclusive process peaks. No new GPU offload claim is made. Current `keep_alive=0` policy unloads after a request: resident warm-model chat was not measured. A warm API process/file cache does not establish warm neural residency.

## Actual final frontend-client workflow

Proof: `.runtime/v45/client_photo_final/verification.json`. Actual shipped TypeScript client under Node performs real HTTP, multipart,202 and SSE; it is not a browser-picker test.

| Work | Actual elapsed |
|---|---:|
| Ordinary first network event |0.048s|
| Ordinary first model text |10.093s|
| Ordinary complete |12.511s|
| PDF / DOCX / XLSX exact source replies |0.278 /0.222 /0.351s|
| Exact CSV statistics |1.093s|
| Background persisted acknowledgement |0.150s|
| Status question during actual deep work |0.825s|
| First verified source facts, polling upper bound |1.433s|
| Generated-photo + manual + CSV investigation |156.584s|
| Actual visual tool |45.953s|
| Actual hypothesis tool |108.516s|
| Saved hypothesis recall without inference |0.198s|

An earlier status phrasing used a model and took70.823s. The corrected route was verified live with `investigation.status` and no `llm.chat`; natural-phrasing regression also passes. These are the same user phrasing, but a different case workload, not a controlled generation benchmark.

## Voice, video and prediction

Proof: `.runtime/v45/network_acceptance/results.json`. Actual6.625second vendor speech fed as back-to-back file PCM over a real WebSocket; it was not paced from a microphone. Silero ready2.234s, first observed speech event2.250s, final transcript6.703s, clean close6.719s. Following real chat completed31.875s (first buffered text31.859s). Kokoro first network bytes36.797s, synthesis/download36.812s. End-to-end75.406s. WAV294233frames at24000Hz. Speech input is a literary vendor utterance, not an industrial accuracy benchmark. The harness synthesized the first240display characters; browser chunk behavior was tested separately. Audible start/barge-in remains unverified.

Video:3actual decoded frame attachments with exact downloaded hashes,2.797s upload/extraction. Twelve selected genuine FD001–FD004 pathways all returned native results: LightGBM5.063–6.765s, BiLSTM-attention10.203–13.219s, ensemble11.094–12.344s. These are inference/smoke timings, not new predictive accuracy metrics. The complete native validation output is machine readable; no synthetic telemetry entered these models.

## Gates and unresolved profiling

The observed0.150s acknowledgement and1.093s deterministic telemetry meet their requested300ms/2s targets on this sample. Ordinary text misses the roughly1–3s aspiration; natural voice's2–5s audible target is neither met nor physically measurable here. Background execution now provides early verified results independent of the slow final diagnosis. One heavy operation at a time and actual cancellation are verified; unrelated process VRAM limits cannot be enforced.

Fresh-process lifespan/startup measured10.750s first and9.657s on repeat with the same disposable state; both native startup probes passed. Proof: `.runtime/v45/startup_benchmark/results.json`. Existing OS caches are not flushed, and the window includes actual native integrity/startup inference. These are ASGI/process measurements, not browser/server-bind or resident-warm-model timings. CPU utilization, isolated SIRE peak RSS, model-specific initialization/prefill/decode, multilingual/noisy ASR quality and clean-machine startup remain unmeasured. Prioritize those measurements before further optimization or enabling larger speech models.

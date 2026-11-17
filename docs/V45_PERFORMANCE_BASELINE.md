# V4.5 baseline measurements

Measured before V4.5 edits against the actual V4 ChatService and installed local Qwen. Proof: `.runtime/v45/performance_baseline.json`; exact benchmark helper retained beside it. Question: “Briefly explain what a rolling bearing does in two sentences.” One observation, no statistically meaningful p95 claim.

| Measurement | Actual result |
|---|---:|
| First in-process event |0.047s|
| First actual model text |10.938s|
| Complete request |13.578s|
| Peak sampled system RAM used |16057610240bytes (15313.730MiB)|
| Peak sampled GPU memory used |348MiB|

Ollama `/api/ps` reported no resident models before this request. This is residency-cold inference; OS disk caches were not flushed. System RAM/GPU include other applications. Sampling every2seconds can miss shorter peaks; these are observed samples, not proven maxima or SIRE-exclusive memory. GPU allocation/offload is not established by installed hardware or total desktop usage.

Initial runtime snapshot: RTX4050,6141MiB GPU total,297MiB used,5%utilization; no resident Ollama model. RAM total16438382592bytes in the actual probe. Baseline runtime/driver snapshots are retained in `runtime_baseline.json`.

Historical V4 combined investigation175.594s and speech/chat/speech83.391s are prior workloads with different inputs/cache state and are not controlled A/B benchmarks. The frozen stress campaign is not a V4.5 performance baseline. Cold/warm OS startup, CPU utilization, separate model load/prefill/decode and physical first-audible latency were not instrumented in this baseline; no estimates replace them.

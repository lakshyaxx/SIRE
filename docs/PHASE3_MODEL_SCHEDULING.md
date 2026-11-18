# Phase 3 model scheduling and resource bounds

The existing central scheduler remains the only heavy-operation scheduler. Its OS file lock coordinates cooperating SIRE processes; active/waiting/recent metrics are per API worker, so an empty local queue does not establish zero system activity. Ollama maximum loaded models=1 and parallel requests=1; configured text/VLM context 4096, GPU keepalive 120 seconds. Switching text↔vision reloads the requested model. Phase 3 does not preload competing models.

One lazy owned media CPU process retains one heavy engine/profile; one lazy owned embedding process retains one MiniLM session. Idle limit 90 seconds. The original prediction workers remain isolated. Media uses existing inference/provider locks and scheduler; embedding uses the same scheduler. Exact-output WAV hits can bypass inference. Fresh embedding queries execute the retained model; persisted document vectors remain fingerprint-bound derived data.

Private IPC request paths are bounded to the owned directory; JSON descriptor/response limits, deadlines, code-generation fingerprints and model hash checks remain. A worker crash/protocol failure can explicitly fall back to the old same-model one-shot path. Cancellation/timeout do not silently retry and integrity failures remain failures. Native packages preload before the reader thread to avoid the observed Windows initialization hang.

On Windows, terminate only an actual owned process tree using its still-owned live Popen handle. Do not terminate by executable name. Launcher PID and actual interpreter PID are separately labeled in request metadata; worker snapshots expose the launcher PID. Actual child-handle cancellation, idle eviction, source changes, timeout, malformed response and busy-parent-EOF exit have process-level regressions. Graceful API shutdown signals requests/jobs before closing workers in a background thread. Abrupt-parent closure makes owned resident workers exit; this is not a claim about every possible third-party/VAD process.

## Actual concurrent behavior

During active structured Qwen inference:

| Concurrent operation | Seconds |
| --- | --- |
| status | 0.010 |
| greeting | 0.075 |
| saved_followup_1 | 0.110 |
| saved_followup_2 | 0.110 |
| upload | 0.081 |
| duplicate_job | 0.026 |

Saved recalls/greeting use no model; status and ordinary document upload remain responsive. Duplicate request IDs return the same durable job rather than repeating it. Model-dependent follow-ups can queue behind a running heavy operation; there is no forced preemption or unlimited concurrency.

Actual active GPU cancellation 0.308s; speech cancellation 0.020s with actual child exit. A real active QA job survived API restart as `interrupted/process_restarted`, without auto-resuming or claiming completion. Existing outage/missing-provider handling returned errors without substituted output.

Peak RSS is observed per-process lifetime; current memory/system peaks/KV split remain null when unmeasured. No deliberate OOM or sustained-load thermal test. CPU/GPU cold costs return after eviction. Same-model fallback can be slower; it preserves correctness and cancellation rather than a latency guarantee.

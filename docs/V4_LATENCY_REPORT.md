# V4 measured latency

Actual local observations, not a controlled performance benchmark. Different attempts/cache states are identified. Most flow measurements have n=1; empirical p50=p95=that observation for n=1, which does not establish tail latency. No representative warm/cold p95 is available.

| Flow | Before / failure | Revised actual result |
|---|---|---|
| CSV description |216.805s, response_limit in upload_e2e_ready |0.446s in compact run;0.854s in reserved-context run, deterministic source statistics/no LLM |
| PDF |71.100s with retrieval/chat in ready run |0.282s exact retrieved excerpts in http_acceptance_verified; no LLM |
| DOCX / XLSX |No paired baseline |0.172s /0.296s exact passage responses |
| Image |92.372s |Ready run:VLM39.547s, retrieval0.016s, chat52.218s; no newer standalone image latency claim |
| Combined investigation |193.784s timeout;195.034s retry timeout;245.645s later invalid structured output |175.594s complete with exact saved vision reuse; profile0.157s, retrieval0.016s, two real proposal rounds173.562s. Not comparable to an uncached fresh-image run. |
| Plain greeting |10.562s actual text model |No revised greeting benchmark; still real model generation |
| Speech/chat/speech |No paired baseline |83.391s total; ASR worker3.562s, chat generation50.312s; remaining transfer/TTS/setup time not separately instrumented. Output WAV11.126667s. Physical first-audible latency unverified. |
| Video first-frame analysis |No paired baseline |40.719s real VLM;3frames actually decoded; other frames not timed with inference |
| Native default FD001/002/003/004 |No new all-route campaign |23.375 /17.531 /10.750 /11.172s, genuine saved histories |

Concrete changes: snapshot files before clearing input; deterministic exact numerical/document routes; omit chart arrays from model context; round-robin compact sources; reserve output space with5000context characters; dynamic0..2 concise hypotheses and650output tokens; controlled response-limit diagnostics; retain successful earlier rounds as partial if follow-up fails. No new model, training, GPU runtime download or shared-service restart.

Provider evidence: previous3906prompt tokens in4096context caused context shifts and timeout. Reduced-context attempt used2040prompt tokens, but a follow-up still consumed all650output tokens and was rejected. Later shorter proposals completed both rounds. Actual Qwen inference is CPU: Ollama size_vram0 at the measured snapshot despite installed RTX4050 hardware. Resource snapshot:RAM16438382592bytes total,1334382592available,91%load; GPU6141MiB total/335MiB used/4%utilization. One snapshot, not a peak measurement. CPU generation around9–10tokens/s appears in provider logs; no general throughput guarantee.

Keep-alive remains0 to release model memory. Cache reuse is explicitly traced, not described as new inference. Numerical source safety takes priority over unverified first-token speed: sensitive prose is buffered for checks. Remaining work: CPU/GPU packaging investigation with explicit installation approval if needed; short conversational budgets; independently measured warm/cold distributions; smaller frontend chunks (current JS788.06kB/239.56kB gzip warning); voice stage/first-audible instrumentation. Existing response/cancellation limits remain enforced.

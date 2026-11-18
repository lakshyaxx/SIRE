# Phase 2 specialist integration

Status names: IMPLEMENTED means actual callable code; VERIFIED means the described real call/control ran; PARTIAL limits quality or scope; DEFERRED means no implementation/acceptance claim; FAILED records an actual unsuccessful attempt. No status substitutes for causal ground truth.

| Specialist | Status | Actual integration / acceptance | Remaining limits |
|---|---|---|---|
| Vision | IMPLEMENTED / VERIFIED; quality PARTIAL | Existing qwen3-vl:2b-instruct, real image + clean schematic + three-frame video calls | Visible observations only; generated photos remain unverified; no hidden-fault proof or gauge accuracy benchmark. |
| ASR / VAD | IMPLEMENTED / VERIFIED; quality PARTIAL | Whisper base.en int8 default; original tiny.en explicit fallback; existing Silero final-utterance WebSocket | Four public transcription references / 59 words; technical/noisy errors remain. Bounded 60s recordings; not unlimited long-form ASR. |
| TTS | IMPLEMENTED / VERIFIED; quality PARTIAL | Existing local Kokoro int8, real configurable voice/speed and completed-sentence WAV SSE | Fresh synthesis slow. Subjective listening and first audible output unverified; no partial-waveform streaming claim. |
| Documents / tables | IMPLEMENTED / VERIFIED; OCR PARTIAL | PDF text, DOCX, XLSX, CSV, TXT, JSON extraction; code-computed statistics and source locators | Scanned/image-only PDF returns explicit 422: no suitable OCR engine installed. Formulas excluded, no inferred units. |
| Video | IMPLEMENTED / VERIFIED; continuous analysis DEFERRED | Existing OpenCV decoder + same vision specialist, max three timestamped frames | Sparse sampled frames cannot establish continuous events; optional audio-track ASR not added. |
| Retrieval | IMPLEMENTED / VERIFIED; relevance quality PARTIAL | Persistent case-isolated MiniLM uint8 CPU vectors + exact lexical/hybrid search | Heuristic similarity threshold; bounded index/chunks; relevance is not semantic entailment or physical truth. |
| NASA prediction | IMPLEMENTED / VERIFIED | All 12 selected FD001–FD004 LightGBM / validated ensemble / BiLSTM paths, genuine saved histories | Compatibility validation enforced; original research and all other catalog routes preserved, not all rebenchmarked. |

Existing providers are extended through `build_registry`, not reimplemented as disconnected services. Registered tools expose real input/output JSON schemas, provider IDs, cancellation and traces. The common response includes the actual run ID, elapsed time, output role, evidence IDs, provider/model/digest and explicit errors. Cached extraction is marked cached, not a new model call; deterministic lexical tools do not pretend an LLM executed.

Integration files: `app/api/specialists.py`, `app/providers/contracts.py`, `app/providers/specialists.py`, existing `app/orchestration/runtime.py` / `tools.py`, `app/media/runtime.py` / `worker.py`, `app/voice/chunks.py`, `app/voice/service.py`, `app/knowledge/*`, `app/evidence/integrity.py` / `tabular.py`, `app/investigation/narrative.py`. Existing FastAPI and frontend routes remain available.

ASR tiny/base mean times on the four referenced recordings: 4.176s / 4.857s. Edits/words: 30/59 versus 11/59. This is a small post-response transcription-reference comparison, not general industrial speech accuracy. No failure-cause evaluator labels were read or ingested.

FAILED attempts preserved: addressed greeting initially invoked Qwen; required visual type initially was optional/misclassified; Tokenizers license guard stopped provisioning; saved ASR trace initially misreported new inference. Fixes and actual reruns are documented in [test report](PHASE2_TEST_REPORT.md). Physical listening and mic/speaker/barge-in acceptance remain unverified for Phase 4.

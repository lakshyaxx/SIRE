# Phase 3 test report

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

Actual network cases use a disposable state namespace guarded by `/api/v1/specialists/contracts`; no synthetic conversations/attachments were inserted into production. Each response has actual elapsed time, tool/provider trace, fixture hashes and output paths. [Machine-readable results and receipt hashes](PHASE3_RESULTS.json).

## Regression coverage

`tests/unit/test_phase3_workers.py`: actual child processes test reuse with fresh request results, source generation changes, deadlines, protocol errors, owned-interpreter cancellation, idle eviction, parent closure during busy work, private request path guards and honest cache metadata. Echo/sleep fixtures are controls for process logic, not model-performance results.

`tests/unit/test_phase3_quality.py`, `test_phase3_routing.py`: stable tie order, incomplete mechanism flags, actual channel-absence contradiction withholding, exact-byte lexicon cache and temperature names; natural saved-hypothesis/finding recall, fresh-analysis exceptions, explicit no-source routing, and audio chunks excluded from document reparse. Existing tests reinforce strict freeform alias restoration/rejection and native inventory paths. Semantic repeat test checks actual model reuse.

## Real model/reliability controls

| Control | Status | Total harness s |
| --- | --- | --- |
| active_gpu_cancel | passed | 5.168 |
| fresh_sentence_stream | passed | 17.724 |
| cancel_active_speech | passed | 4.068 |
| cached_sentence_stream | passed | 0.422 |
| concurrent_status_upload_recall_dedup | passed | 13.999 |
| actual_unavailable_tag | passed | 0.168 |

Cancellation measured after observed active GPU lease/positive VRAM, and speech cancellation checked actual interpreter exit. Complete fresh sentence-stream WAVs, exact cached WAV replay, concurrent status/greeting/upload/saved recalls, duplicate job deduplication and unavailable real tag exercised actual interfaces. Restart interrupted a real active disposable job; recovery retained `interrupted/process_restarted`. Explicit resident-entrypoint failure used real one-shot same-model fallback and a decoded WAV, not dummy output.

Offline check denies external Python DNS/socket access in a dedicated process and inherited Python workers, while permitting local Ollama. Real Qwen, MiniLM, Kokoro, Whisper and genuine FD001 inference pass; refused local endpoint fails explicitly. This is not OS-level air-gap proof or assurance about an already-running Ollama process's egress.

## Failures retained and corrected

The first optimized profile hit a native import-order stall; preserved under `after/`. Initial reliability run exposed mixed-history recall and audio-as-document defects; fixed and real rerun passes. Offline adapter first passed a model descriptor instead of an ID; corrected then reran actual inference. Initial full suite had one failure because a Popen test double also intercepted taskkill and spawned extra sleepers; intercept narrowed to native-worker launches, with the original three-second cancellation assertion retained. Final full suite above passes. Failed receipts were not converted into invented passes.

Initial production exact-equality audit failed because live user activity appended records; investigated with zero original row changes/deletions, qualified receipt retained. Immediate cutover equality is15/15. [Preservation](PHASE3_ARTIFACT_AUDIT.md).

Existing warning: Starlette/AnyIO BlockingPortal deprecation. Vite reports its existing >500kB chunk advisory. Neither is concealed as a clean warning-free result. No physical browser/mic/speaker or independent semantic-cause acceptance claimed.

## Reproduction

Use the preserved root environment and existing installed weights; no model downloads:

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check app tests scripts
.venv/Scripts/python.exe -m black --check app tests scripts
.venv/Scripts/python.exe -m pip check
cd web
npm test
npm run build
```

For network profiling use `scripts/profile_phase3.py --help`, `scripts/phase3_reliability.py --help` and `scripts/phase3_offline_acceptance.py --help` against a separately started loopback8001 factory server with a new `.runtime` state directory. Namespace guards reject production; output directories must be fresh. Public corpus path is explicit and evaluator-only directories must remain external. Do not copy private QA IDs into production. Exact recorded conditions and raw trace paths remain in the receipts.

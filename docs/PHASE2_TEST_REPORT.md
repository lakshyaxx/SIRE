# Phase 2 test report

Checkpoint 2026-11-18T12:23:47+05:30. Raw evidence is private under `.runtime/phase2_20261118/`; hashes/fixture IDs/timings/status scopes are exported in [machine-readable summary](PHASE2_VALIDATION_SUMMARY.json). No hidden cause-truth scoring or full stress-lab rerun was performed.

| Check | Actual result |
|---|---|
| Fresh baseline `python -m pytest -q` | 293passed /1warning /153.75s |
| Final full `python -m pytest -q` | **313passed /1warning /165.01s** |
| Resumed `npm test` | **13passed /0failed /940.6423ms** |
| Resumed `npm run build` | TypeScript passed;646modules;13.87s |
| Resumed Ruff | All checks passed |
| Resumed Black |95files unchanged |
| Root `python -m pip check` | No broken requirements found |
| Main loaded-code/assets/DB audit | Exact current source identity;2served assets byte-identical;15production tables exact |

One existing Starlette/AnyIO deprecation warning and the existing801.51kB frontend chunk advisory remain. Unit/control tests include deterministic fixtures where appropriate; the modality acceptance below used actual files, model workers and local HTTP/WS connections. They are not mocked integration passes.

| # | Required acceptance | Result / scope | Actual proof and limitation |
|---:|---|---|---|
| 1 | Ordinary greeting | VERIFIED | `stage_c_retest.json` — Addressed greetings 0 model calls; initial failure retained and fixed. |
| 2 | Documented SIRE capabilities | VERIFIED | `stage_c/results.json` — Actual capability manifest; no invented self-description. |
| 3 | Image-only inspection | VERIFIED / quality PARTIAL | `stage_c_retest.json; final_controls.json` — Photo / schematic distinction, original source IDs; visual interpretation unverified. |
| 4 | PDF maintenance analysis | VERIFIED / scanned OCR unavailable | `stage_c/results.json; browser_acceptance.json` — Text extraction and real cited browser response; no scanned-text substitute. |
| 5 | CSV statistics | VERIFIED | `stage_c/results.json; claim_controls.json` — Code-computed values and source-row identities. |
| 6 | XLSX interpretation | VERIFIED | `stage_c/results.json` — Numeric column statistics with sheet/cell locators; formulas excluded. |
| 7 | Short speech transcription | VERIFIED | `stage_d_results.json` — Actual original WAV and model identity; input provenance. |
| 8 | Industrial speech | VERIFIED execution / quality PARTIAL | `asr_comparison.json; asr_evaluation.json` — Actual tiny/base comparison; small post-response public transcription-reference evaluation. |
| 9 | New speech synthesis | VERIFIED / listening unverified | `stage_d_results.json` — Actual WAV hashes/frames, first completed segment and total latency; no fake audio. |
| 10 | Industrial video | VERIFIED / continuous analysis DEFERRED | `stage_c/results.json` — Real decoder frames with timestamps; three bounded child vision calls. |
| 11 | Multiple-document retrieval | VERIFIED | `multidoc.json` — Three actual documents, hybrid concepts and exact PUMP-001 retrieval; historical cutoff yields zero future passages. |
| 12 | Duplicate measurements | VERIFIED | `stage_e/results.json; claim_controls.json` — Equivalent CSV/JSON source rows retain one measurement origin, not independent corroboration. |
| 13 | Contradictory sensor/document evidence | VERIFIED numeric controls and two quoted accounts / broad quality PARTIAL | `claim_controls.json; multidoc.json; contradiction_acceptance.json; conflict_quote_verification.json` — Wrong value/unit contradicted; wrong asset and future source withheld. Real final answer cites both opposing accounts; both exact quotes independently match original document excerpts. Neither account is physically authenticated. |
| 14 | Photo + PDF + CSV investigation | VERIFIED execution / cause quality PARTIAL | `stage_e/results.json` — Complete actual job including equivalent JSON duplicate; source identity retained. |
| 15 | Video + sensor investigation | VERIFIED execution / cause quality PARTIAL | `stage_e/results.json` — Complete actual job with original frame and sensor identities. |
| 16 | Saved RUL predictions | VERIFIED | `stage_c/results.json` — Twelve selected primary pathways; no synthetic oil-rig rows sent to NASA models. |
| 17 | Malformed/unsupported files | VERIFIED | `final_controls.json` — Invalid and image-only PDF explicitly 422; no fabricated extraction. |
| 18 | Model outage | VERIFIED | `final_controls.json; offline/results.json` — Actual nonexistent tag and refused local endpoint; no substituted model response. |
| 19 | Offline operation | VERIFIED within process guard | `offline/results.json` — External Python sockets/DNS denied; real local Qwen, embeddings and native prediction work. Not an OS-wide air-gap claim. |
| 20 | Active model cancellation | VERIFIED | `final_controls.json` — Observed active GPU-resident vision request cancelled; lease released. |
| 21 | Cold/warm repetition | VERIFIED | `final_performance.json` — Actual unloaded residency then resident repeat; OS caches not flushed. |
| 22 | Fast conversation during deep work | VERIFIED | `stage_e/results.json` — Same-case greetings while scheduler was actually busy; no LLM. |

Regression modules added: `test_phase2_contracts.py` (schemas/scopes/addressed greetings/pure versus compound transcription), `test_phase2_integrity.py` (changed bytes/forged chunks/chunk bounds/fragment review/OS counters), `test_phase2_semantic.py` (actual optional embeddings, case isolation, persistence, cutoff/rebuild, missing model), `test_phase2_tabular.py` (safe CSV/XLSX/formula/cell semantics). Existing speech cache/voice session tests now check voice-speed key isolation and truthful cached ASR provenance. No research predictor/preprocessing was modified.

Reproducible local commands from the existing prepared checkout:

```text
.venv/Scripts/python.exe -m pytest -q
cd web
npm test
npm run build
```

Optional local candidate review: `python scripts/setup_phase2_specialists.py`; install only with explicit `--install`. Actual API scripts: `scripts/phase2_acceptance.py`, `phase2_composition_acceptance.py`, `phase2_offline_acceptance.py`. Invoke `--help` for corpus/state/output arguments. The first two verify the real8001 state namespace before mutations and require fresh output paths; never run them against production. Only the isolated public-input corpus is allowed; never pass an evaluator directory. Offline acceptance denies external Python sockets in its owned process/children, not OS-wide networking.

Reproduced defects and fixes:

1. Addressed `Hello, SIRE` initially called Qwen in7.547s: generalized punctuation/vocative routing in configuration; actual no-model retests plus regression guard for engineering input.
2. Optional visual category allowed ambiguous/misassigned category/component: required schema and explicit component instructions; policy fingerprint now invalidates old cached interpretations. Actual reruns identify photograph/bearing and clean schematic, without claiming visual accuracy universally.
3. Existing saved ASR initially claimed fresh model execution and Qwen top metadata: general cached-extraction/deterministic provenance fix; actual pure-transcription response0.145s, no new NN call. Original failed control saved.
4. Potential source-byte/chunk tampering paths: verify original bytes before cache/use and reproduce chunks before retrieval. Changed-source/forged-chunk regression cases withhold evidence.
5. Hypothesis follow-up retrieval could block the async loop: run source retrieval off loop and bridge cancellation. Same-case fast conversation verified during actual heavy jobs.
6. Speech output cache initially exposed original worker counters as current execution: separate original synthesis resources, mark cached worker not started. Exact WAVs verified on repeated delivery.
7. Final contradictory-document control initially failed at384tokens and retrieval omitted the opposing short account. A first bounded-excerpt/output-budget fix completed but still lacked that account; this intermediate semantic failure is retained. Filename relevance ranking with exact-body eligibility, two-document-passage context retention and a650token evidence-only budget now return both opposing operator quotes in the real rerun. Both quotes independently match their original cited document excerpts; no validator was disabled. New regressions cover named-document account selection, source-context retention and scoped output budgets.

Failed attempts remain in `stage_c/results.json`, `final_controls_first_attempt.json`, `control_failure_history.json`, `contradiction_acceptance_first_attempt.json`, `contradiction_acceptance_context_only.json` and provisioning history. None was erased or counted as an original pass. An early QA restart probe also received a real connection refusal before startup completed; readiness is now observed before execution.

Actual Brave QA acceptance: typed greeting, real native file picker,2870bytePDF ready receipt, cited response and source-inspection drawer. Persisted QA messages corroborate UI. Server greeting0.094s and PDF reply10.984s are server metrics; frontend rounded upload0.09s is not independent network timing. Final production-browser navigation was stopped by Computer Use security because current URL could not be confidently determined; no bypass attempted. Production API/source/frontend-byte checks passed. Physical mic/speaker/noise/barge-in and subjective listening remain unverified, allowed Phase4 limits under the directive.

Known gaps: noisy/technical ASR quality, no OCR engine, sparse rather than continuous video, qualitative causal/contradiction accuracy, exact per-specialist cold/warm/CPU utilization coverage, clean-host portability and broader visual robustness. These are not fabricated passes or calibrated diagnostic scores.

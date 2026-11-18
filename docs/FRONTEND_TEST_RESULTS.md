# Frontend integration — measured verification

## Reproducible commands and actual output

| Command | Actual result |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest -q` | **346 passed,1 warning,157.95s** |
| `npm --prefix web run test` | **24 passed,0 failed,3313.3591ms** |
| `$env:SIRE_BUILD_DIR='dist-v3'; npm --prefix web run build` | TypeScript passes; Vite2794 modules, build12.20s, main537.94kB, lazy chart327.46kB |
| `python -m ruff check app tests scripts` | All checks passed |
| `python -m black --check app tests scripts` | Clean after final main.py formatting |
| `python -m pip check` | No broken requirements found |
| `scripts/profile_phase3.py` against guarded QA8001 | All24 actual cases passed |
| Private `frontend_native_routes.py` | All12 selected dataset/role routes passed |
| `scripts/phase3_offline_acceptance.py --output …` | All7 actual checks passed with external Python sockets/DNS denied |
| Final private preservation/compatibility audit | 813 native hashes,7956 frozen files; all15 original tables exact; 6 existing case formats and28 original attachments readable on a clone |

The existing Starlette/AnyIO BlockingPortal deprecation remains one backend warning. ReactRouter/Lucide use-client directives are ignored by Rollup in the existing build; the >500kB main chunk advisory remains. These warnings are not hidden or treated as full performance acceptance.

The formatter exposed an old source-string-based voice assertion. It was replaced with TypeScript AST extraction of the actual speech-started branch so formatting cannot accidentally make that regression inspect an empty substring. Final suite has zero failures. Backend and frontend logs retain the earlier failure and correction context in the work session; final logs contain actual final runs.

## Actual network measurements

Single serial workload on the shared local workstation; these are observations, not SLAs or comparative speedup claims. No user-browser rendering time or audible output time is inferred from API timings.

| Actual case | Full seconds | Result |
| --- | --- | --- |
| text_cold | 5.918872 | passed |
| text_warm | 1.030738 | passed |
| greeting | 0.069353 | passed |
| capabilities | 0.092819 | passed |
| pdf | 0.197788 | passed |
| csv | 0.538839 | passed |
| xlsx | 2.640362 | passed |
| docx | 0.536954 | passed |
| retrieval_first | 2.054097 | passed |
| retrieval_repeat | 0.334531 | passed |
| asr_short | 0.109065 | passed |
| asr_technical_base | 0.106898 | passed |
| asr_technical_tiny | 0.098398 | passed |
| tts_0 | 8.776786 | passed |
| tts_1 | 5.721433 | passed |
| tts_2 | 11.059158 | passed |
| tts_3 | 27.522490 | passed |
| image | 10.494124 | passed |
| vision_to_text | 6.971204 | passed |
| video | 17.986949 | passed |
| rul_low_latency | 5.833470 | passed |
| rul_advanced | 12.878109 | passed |
| rul_deep | 9.371608 | passed |
| deep | 24.694163 | passed |

Cold/warm here describe the measured paired workload; inspect actual Ollama load/prefill/token timings and traces in the raw output rather than treating every cold state as identical. ASR cached-read cases are distinct from fresh ASR at ingestion/offline-process measurement.

## Supported browser observations

| Check | Result | Observed evidence |
| --- | --- | --- |
| backend_outage | passed | Refresh checks displayed Disconnected / Not connected / Failed to fetch after verified idle QA shutdown. |
| missing_configured_model | passed | Configured model unavailable; actual submitted general question returned Selected local model is not installed without a fabricated reply. |
| saved_case_restart_details_trace_export | passed | Persisted report displayed human-readable source values, complete stage, expanded hypothesis support/contradictions, actual execution trace and downloaded PDF. |
| canonical_csv_source | passed | Clicked actual evidence reference; library resolved original telemetry CSV and exact source record. |
| fd001_browser_prediction_and_comparison | passed | Actual saved-model inference on FD001-ENGINE-001 plus two selected saved predictors, operating cycles and provenance shown. |
| fd004_browser_dataset_change | passed | Dataset selection cleared prior results; FD004-ENGINE-001 returned actual FD004 prediction and provenance. |
| scenario_what_if | passed | Actual same-seed fenced scenario trajectories, hashes, limitations and evidence ID returned. |
| cancel_running_job | observed_terminal | cancelled |
| responsive_layouts | passed | 1366 and 1920 desktop plus 390 phone and 768 tablet checked. No horizontal document overflow measured. 1366 sidebar footer bottom 760.9999847412109 within 768. Phone menu opens and navigates. |
| physical_voice | unverified | Local live/session controls rendered; physical microphone permission, acoustic playback, genuine interruption and noise acceptance were not exercised. |
| greeting_general_and_manifest | passed | Earlier browser greeting, source-backed SIRE description and real general Qwen follow-up completed with shared history. |
| first_upload_after_new_conversation_fix | passed | Real generated-image upload persisted through URL transition; VLM/text completed; Inspector showed exact unverified model provenance. |
| three_file_browser_investigation | passed | PDF/CSV/XLSX selected through browser chooser, ingested and investigated; real report remained after restart. |
| case_history | passed | Actual completed and cancelled QA jobs displayed with source counts and links. |
| production_final_render | passed | Read-only final check on normal port8000: integrated Assistant, ready backend, message composer and loaded local branding; no QA message submitted. |

Earlier in the same integration session: greeting, SIRE capability-manifest explanation and a genuine Qwen general follow-up completed in conversation166048f4df594acc97869cbba61bd6d6. Generated-image upload followed by real vision/text completed in f0623c7ae05a484f98f4a1ac49d51a1a; canonical Inspector showed model-generated/unverified provenance. The three-file PDF/CSV/XLSX browser form created actual job1f3025a015d34d95b74c99f812267a07 and saved casea7cfd4e0084c4635ae222572c6da17d4. Their IDs, raw outputs and histories remain in the disposable QA database. Wall-clock browser TTFT was not instrumented and is not invented here.

Unconfirmed: physical mic/speaker/autoplay/barge-in/noise, broad accessibility/screen-reader matrix, every hardware/browser combination and semantic/physical diagnostic accuracy. Model-generated check/question strings can truncate at configured bounds; no fabricated completion or validated-cause label is substituted. Referenced source identity is not proof that every model claim is supported by that source.

Private actual JSON/logs/screenshots: `.runtime/frontend_integration_20261119_005543/`. Public repository summary: `FRONTEND_INTEGRATION_RESULTS.json`. No evaluator-only content or test truth is included.

# SIRE general reliability release 4.8.3

Release verified 2026-11-19T02:48:29.389849+00:00. SIRE is running through the normal local launcher at http://127.0.0.1:8000. Development is frozen for the showcase. This report concerns the current general reliability directive; earlier stabilization/stress reports remain historical evidence.

**Decision: suitable for a supervised local demonstration that shows uncertainty and partial results. General diagnostic correctness remains a KNOWN LIMITATION.** No evidence supports an autonomous engineering sign-off or a guaranteed correct diagnosis.

## Workflow assessment

| Workflow | Assessment | Actual evidence and limit |
|---|---|---|
| Normal startup / frontend | PASS | API and visible browser diagnostics show 4.8.3; served static index exactly matches built index; correct production namespace. |
| Numeric rejection and source agreement | PASS | Deterministic regression cases cover user-report provenance, units, timestamps, ranges, unsupported values and paragraph isolation; source authenticity remains unverified. |
| Candidate failure isolation | PASS | Valid candidates/facts survive another invalid candidate or a failed bounded repair; complete/partial/error remain distinct. |
| Text-only investigation transport | PASS | All five unfamiliar text cases returned persisted structured results without a crash. |
| General hypothesis and causal quality | KNOWN LIMITATION | Two complete and four partial results across six real investigations; plausible-looking mechanisms and source links do not establish a physical cause. |
| Fresh CSV/PDF/image upload and links | PASS | Actual browser upload retained all three attachment IDs, FAN-042 identity, source statistics, report and execution trace; source link verified after reload. |
| Multimodal diagnostic conclusions | KNOWN LIMITATION | Original-source replay retained zero hypotheses; separate fresh browser run retained one tentative hypothesis. Both honestly partial. |
| Saved-case follow-up identity | PASS | Three actual follow-ups selected the same saved ROAD-219 case, with no new investigation tools and no false claim that the case was absent. |
| Follow-up explanation correctness | KNOWN LIMITATION | Two complete and one partial; unsupported thermostat numeric example withheld. Analogies/qualitative causal links are not fully verified. |
| Citation ID resolution | PASS | Four distinct retained supporting references resolved with HTTP 200; exact evidence inspector opened the selected CSV channel. |
| Citation semantic support | KNOWN LIMITATION | No calibrated support rate measured. A citation or numeric match cannot certify every qualitative statement. |
| Protected models / production | PASS | 813 native and 7,956 frozen files checked without mismatches; all 15 production tables have identical canonical row hashes. |
| Local offline components | PASS, bounded | Seven actual process-scoped guarded checks passed; not an OS-wide air-gap claim. |
| Physical live voice / mobile | KNOWN LIMITATION | No fresh physical microphone, speaker, background-noise, barge-in or mobile acceptance in this release. |
| Old browser tab during rebuild | FAIL, recovered | Expired dynamic-import chunk failed in a pre-rebuild QA tab; reloading loaded current assets and opened evidence successfully. Automatic stale-chunk recovery deferred. |

## Confirmed root causes and changes

1. **Numeric source interpretation:** the source-ID matcher excluded real `user:` references; some quantity units were not screened; only one range endpoint or the wrong clause timestamp could be checked. Aggregation labels leaked across neighboring clauses, and an unrelated cited unit could prematurely reject a supported value. The verifier now records the exact claim, source IDs, value, unit, timestamp/statistic, source value and reason; notation aliases are configuration-driven, with no implicit unit-scale conversion. User-reported values can be `supported_contextually`, never independently measured merely because a user typed them. Nonfinite model values produce diagnostics instead of crashing validation.
2. **Excessive failure scope:** a bad numeric field aborted an entire proposal/chat answer. Hypothesis mechanism, assumptions, expected predicates and tests are now checked per candidate. Unsupported chat paragraphs are withheld while safe paragraphs/source facts survive, with a truthful partial state. Original rejected text and reasons remain in private traces; nothing is fabricated to fill a missing candidate.
3. **Repair lost useful work:** failed or malformed repair could erase a valid completed draft. At most one repair is allowed on the initial proposal; valid siblings remain if it fails. Later evidence/retrieval rounds do not gain an extra retry and preserve earlier completed results. Short fields were constrained to 120 characters; configured 200-character short fields now permit complete assumptions/tests. Existing 1,600-token proposal cap and concise mechanism cap remain. Real Qwen still sometimes exceeds quality/semantic limits; these are reported, not labeled fixed.
4. **Evidence roles:** missing measurements and command states could be promoted to observations; assumptions/expected test signs were also being overchecked as observed facts. Role checks now preserve the distinction. Expected signs and assumptions are displayed separately from observed or missing facts. Unknown measurements never become positive proof. Generic guidance replaces equipment-specific tuning; this is a bounded validator, not a complete physics proof system.
5. **Memory and identity:** actual CAR-101 case data existed while saved asset identity was null; work-order/technician identifiers interfered with equipment extraction and a named follow-up was then dropped as mismatched. Explicit equipment declarations take priority. Legacy identity is recovered in memory from the actual saved question; production cases are not rewritten. Named older cases are selectable beyond the previous 20-case window. Failed-request provenance is recovered from actual linked jobs/runs/messages without inventing a completed investigation. New messages retain request IDs. Context budgets trim whole conversational pairs.
6. **Misleading partial UI:** reopened reports with quality issues were listed as complete, and the detail banner labeled useful partial results as failed. Read-only indexes and the workspace now expose partial status and exact failed stage; assumptions and expected signs have their correct display roles. Exact repeated follow-up warnings are deduplicated for presentation, while raw traces are preserved.
7. **Reference parsing:** bracketed prose containing hyphenated C-MAPSS text was mistaken for a citation range. Alias/range detection is narrowed while unknown 32-character attachment identifiers still fail reference validation. Citation verification was not disabled.

## Verification results

| Check | Actual result |
|---|---|
| Before-task backend baseline | 383 passed, 1 warning; 194.84 seconds |
| Final complete backend suite | 418 passed, 1 warning; 164.16 seconds |
| Frontend baseline / final | 27 / 29 passed; final zero failures, skips or cancellations |
| Frontend production build | TypeScript/build succeeded; Vite 12.64 seconds |
| Resume formatting-only regression rerun | 35 passed, 1 warning; 4.26 seconds |
| Formatting / lint | Black check: 13 files unchanged; Ruff: all checks passed |
| Dependencies | pip check: No broken requirements found |

The warning is the existing Starlette/AnyIO deprecation. Vite also reports its existing large-chunk advisory. The 35 new backend cases and two frontend tests cover invalid JSON/one retry, numeric candidate isolation, failed repair retention, unknown references, both range endpoints, source/time/unit binding, missing/duplicate/contradictory measurements, role boundaries, explicit/nonnumeric identifiers, legacy/failed context and partial reopening. The existing numeric-failure test now expects an honest partial result while still rejecting the bad value and retaining actual source statistics.

One intermediate concurrent backend run failed `test_model_discovery_does_not_block_the_async_request_loop` while real inference held the shared model lease. Its cleanup also attempted to close an active generator. No test was disabled and no scheduler safeguard bypassed. The isolated idle rerun passed in 0.93 seconds, followed by the complete 418-pass idle suite above. This release does not claim that timing assertion is reliable under concurrent external inference.

## Genuine Qwen runs

These are real local HTTP/SSE calls in a disposable QA database, using `qwen3:4b-instruct`; no model responses were substituted. Structured/raw streamed outputs and real execution traces are preserved. COMPLETE means the bounded workflow returned without reported field rejection, not that a cause is established.

| Case / requested asset | Actual status | Retained hypotheses | First report/text observed (s) | Full response (s) |
|---|---|---:|---:|---:|
| unfamiliar_fan / BLOWER-26 | complete | 3 | 19.507 | 19.691 |
| quantified_water_pump / WATER-63 | partial | 1 | 40.395 | 40.572 |
| car_after_service / ROAD-219 | partial | 5 | 40.273 | 40.470 |
| hydraulic_press / PRESS-62 | complete | 3 | 14.061 | 14.261 |
| electrical_motor / DRIVE-18 | partial | 4 | 37.305 | 37.519 |
| original_multimodal_fan / FAN-042 | partial | 0 | 0.456 | 22.258 |

Job observations were polled, so these first-report figures are not GPU time-to-first-token measurements. The original multimodal replay exposed deterministic findings early and used saved original source processing; it is distinct from the fresh browser ingestion below. Repairs explain part of the longer text-only runs. No fast-route timings are substituted for these Qwen measurements.

| Actual ROAD-219 follow-up | Status | First visible text (s) | Full response (s) |
|---|---|---:|---:|
| Explain the ROAD-219 investigation in simple language for the owner. | complete | 3.434 | 3.435 |
| The second possibility was confusing. Explain it with an everyday analogy, keeping assumptions separate from facts. | complete | 3.098 | 3.099 |
| What further evidence would distinguish the remaining possibilities? | partial | 3.656 | 3.657 |

All follow-ups used `evidence_conversation`, model `qwen3:4b-instruct`, saved case `49f9bd4bf1f240c38c05a54bb242fc0d`, asset ROAD-219 and zero investigation tools. The third model response supplied an uncited 80–90 °C example; both endpoints were detected and that paragraph was withheld, retaining safe content. Raw provider first-token and prompt/output metrics are in the machine-readable results; visible text is intentionally buffered for validation.

### Fresh browser upload

Actual test URL: `http://127.0.0.1:8001/investigations/e2343d62bf044154b297b11b6619b2f3`. Saved case: `e2343d62bf044154b297b11b6619b2f3`. Conversation: `0afb024cf193463e969e09d71e6b7905`. All three attachments were confirmed by backend association, not inferred solely from UI chips:

| File | Actual attachment ID |
|---|---|
| FAN-042_sensor_history.csv | 85a52f67c1a045d181cf390bdb691d04 |
| FAN-042_maintenance_notes.pdf | 41a80ea4a19b4ef19e68adc05f4f66b1 |
| FAN-042_inspection.png | f33df7708b3a4b9eae4859bbcffe34f8 |

Result: PARTIAL, one tentative hypothesis, failed stage `hypotheses.quality`. The banner explicitly showed partial findings, not total failure. PDF conflict and missing-input text, computed channel observations, unverified image output, original-source links and execution trace were visible. Image normalization changes stored image bytes; metadata retains the original uploaded SHA-256, verified against the fixture. `real_uploaded` denotes the transport source, not authentic physical measurements; these fixtures explicitly remain synthetic/unverified.

An old QA tab requested a removed build chunk while following a source link. A full reload recovered; the evidence inspector then displayed the exact inlet-filter differential-pressure source, rows and aggregation scope. No production records were created during browser checks. The QA server was stopped only after confirming zero active QA jobs; the production server remains running. [Partial investigation screenshot](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/.runtime/reliability_20261119_055333/browser-investigation.jpg>); [Production 4.8.3 screenshot](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/.runtime/reliability_20261119_055333/browser-production-status.jpg>).

### Independent CSV recomputation

24 source rows, six channels, 143 finite numeric readings. The vibration series has one missing sample at 2026-11-18 14:00 UTC and was not imputed. Baseline uses up to the first 24 valid readings; recent uses the last six valid readings. Here the baseline spans the whole supplied window, not an independently established healthy baseline. Exact values/IDs are in the saved fixture verification.

| Channel | Unit | Count | Baseline mean | Recent mean | Delta | Missing |
|---|---|---:|---:|---:|---:|---:|
| vibration | mm/s RMS | 23 | 2.576087 | 4.126667 | 1.550580 | 1 |
| bearing_temp | degC | 24 | 56.537500 | 68.566667 | 12.029167 | 0 |
| airflow | m3/h | 24 | 11300.833333 | 10140.000000 | -1160.833333 | 0 |
| current | A | 24 | 16.337500 | 17.600000 | 1.262500 | 0 |
| speed | rpm | 24 | 1464.625000 | 1464.166667 | -0.458333 | 0 |
| inlet_filter_dp | kPa | 24 | 0.965833 | 1.336667 | 0.370833 | 0 |

These deterministic statistics matched an independent Python CSV calculation. Four retained source IDs resolved HTTP 200. This is not a semantic citation-support rate, model fault-accuracy score or calibrated confidence measurement; those metrics are unmeasured.

### Local component checks

| Actual check | Result | Wall seconds |
|---|---|---:|
| external_dns_denied | PASS | 0.000 |
| actual_local_qwen | PASS | 4.354 |
| actual_local_embeddings | PASS | 1.287 |
| actual_local_speech | PASS | 10.664 |
| actual_local_asr | PASS | 2.403 |
| actual_saved_native | PASS | 6.890 |
| actual_refused_loopback | PASS | 2.537 |

The guard denied external Python sockets/DNS while allowing local Ollama, including inherited Python workers. It does not prove OS-wide isolation or prohibit egress from an already-running Ollama process. TTS generated an actual WAV; ASR transcribed that WAV. This does not certify a physical live-voice interaction. The native prediction used a genuine compatible saved FD001 sample; no synthetic industrial telemetry was sent to C-MAPSS, no accuracy claim is inferred and no training was performed.

## Changed files and reproducible commands

Compared against the exact dirty-workspace checkpoint rather than assuming HEAD was the starting application:

- [app/api/frontend.py](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/app/api/frontend.py>)
- [app/api/main.py](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/app/api/main.py>)
- [app/chat/service.py](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/app/chat/service.py>)
- [app/evidence/context.py](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/app/evidence/context.py>)
- [app/evidence/verification.py](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/app/evidence/verification.py>)
- [app/investigation/engine.py](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/app/investigation/engine.py>)
- [app/investigation/narrative.py](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/app/investigation/narrative.py>)
- [app/investigation/proposal_schema.py](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/app/investigation/proposal_schema.py>)
- [app/orchestration/case_context.py](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/app/orchestration/case_context.py>)
- [app/orchestration/tools.py](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/app/orchestration/tools.py>)
- [app/orchestration/understanding.py](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/app/orchestration/understanding.py>)
- [config/app.yaml](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/config/app.yaml>)
- [config/capabilities.yaml](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/config/capabilities.yaml>)
- [tests/unit/test_v4_verification.py](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/tests/unit/test_v4_verification.py>)
- [web/src/pages/InvestigationWorkspace.tsx](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/web/src/pages/InvestigationWorkspace.tsx>)
- [web/src/services/api.ts](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/web/src/services/api.ts>)
- [web/src/types/api.ts](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/web/src/types/api.ts>)
- [tests/unit/test_reliability_general.py](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/tests/unit/test_reliability_general.py>)
- [web/tests/reliability.test.mjs](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/web/tests/reliability.test.mjs>)

New release documents: [RELIABILITY_FIX_REPORT.md](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/docs/RELIABILITY_FIX_REPORT.md>) and [RELIABILITY_FIX_RESULTS.json](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/docs/RELIABILITY_FIX_RESULTS.json>). Earlier dirty files and research were preserved. Private audit/replay/checkpoint helpers and full source/raw-output traces live in [the ignored evidence directory](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/.runtime/reliability_20261119_055333>).

Commands run from `C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE`:

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m pytest tests/unit/test_reliability_general.py -q
.venv/Scripts/python.exe -m pytest tests/unit/test_performance_cache.py::test_model_discovery_does_not_block_the_async_request_loop -q
```

Frontend commands run in `C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/web`: `npm test`; `npm run build` with the staged `dist-v3` output, then copy verified built assets into the normal `dist` directory. TypeScript runs as part of build. Ruff/Black were run on the 13 changed Python/test files; `python -m pip check` verified the preserved environment. Private actual-network replays/checks: `.venv/Scripts/python.exe .runtime/reliability_acceptance.py`, `reliability_fixture_verify.py`, `reliability_protection.py`, `reliability_preserve.py` and `reliability_release_verify.py` (all in the same `.runtime` directory). Original private fixtures and QA setup are required; a clean clone deliberately does not include user uploads/weights.

Normal launcher: set `SIRE_STATE_DIR` to the existing `.runtime/v2` absolute path and `SIRE_WEB_BUILD=dist`, then `.venv/Scripts/python.exe scripts/dev.py`. It is already running; do not start a competing launcher. The production health response confirmed all existing text/vision tags and native readiness; the static index and production namespace were checked independently.

## Preservation, corrected attempts and remaining work

Checkpoint ref: `codex/reliability-checkpoint-20261119_055333`, HEAD `174cea7978698606e475c893ee52ef468c7c4dab`. Since that HEAD had prior uncommitted stabilization changes, `working_source_before.zip` plus `working_tree.patch` are the exact recoverable starting source; their hashes are preserved in baseline metadata. Original production SQLite backup and old static build also remain private. Never restore the database over later user data to roll back code.

All 15 production tables retain identical row counts and content hashes; 813 native artifacts and 7,956 frozen files have zero manifest mismatches. No dependencies/models were downloaded, no tuning/training occurred, and no research or frozen results were removed or published. No evaluator-only content was ingested or used to score these new cases.

During implementation an overly strict assumption/expected-sign check was corrected, an extra retrieval-round repair was removed, and compatibility with older saved cases missing a question field was restored. The resulting existing suites pass. No architecture rollback, model change, guardrail disablement or broad refactor was used. On resume only the new test file's import placement/Black formatting changed, and its 35 cases were rerun; application logic stayed frozen.

Remaining priorities after the showcase: (1) independently assess qualitative source support and causal reasoning, including contradictory records and hydraulic relationships; (2) evaluate semantic hypothesis deduplication and explanation/analogy quality without hiding partial cases; (3) physical microphone/speaker/barge-in/noise/mobile acceptance; (4) optional stale-build tab recovery and contention-test isolation. They are deferred rather than presented as complete. The small local model may still produce wrong-source/rounded statistics or unsupported interpretations, and a run may legitimately retain no hypotheses. Do not force a diagnosis or reinterpret heuristic rank as probability.

No further user information is required to use the verified local build. The next step is the supervised showcase with the present frozen release. Full paths, IDs, actual results and artifact hashes are in [RELIABILITY_FIX_RESULTS.json](<C:/Users/laksh/OneDrive/Desktop/SIRE/SIRE/docs/RELIABILITY_FIX_RESULTS.json>).

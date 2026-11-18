# PUMP-017 investigation release fix — 2026-11-19

SIRE **4.8.1** is running through the normal local launcher on `http://127.0.0.1:8000`. The verified original routing failure is repaired. Exact stored-source replay and fresh browser/backend investigation completed. All original production rows and source bytes remain unchanged. The original failed record remains an error from its original execution; it was not overwritten with a fabricated successful result.

## Original evidence and exact failure

The displayed ID `a9923c9f3cb342dcaf3b036ce638986b` is a durable job ID, in conversation `e9ee08b4301449e09e7923ebd34ffbb4`. Its run `b22a280b-9ec5-416a-a3c2-b700f940b6c9` finished with **zero executed tool spans**. The planner correctly chose `incident_investigation`, but a later global regex matched `calculate unsupported remaining useful life` inside the user's exclusion `Do not assume a confirmed root cause, calculate unsupported remaining useful life, or recommend operating changes...`. It raised `rul_requires_sensor_tool` before CSV profiling, vision, retrieval or hypothesis generation. No NASA prediction ran. No completed hypothesis Case/report had yet been created. There were no original model outputs to inspect because the request stopped before model execution.

All three uploads reached the backend and their IDs were saved in the original user and assistant metadata. The original effective request was reconstructed from those actual records/defaults and verified against the persisted request-body SHA-256: `48885c0820293e02779e460d58cbaa258fcec4f85a0ad26f489abe38bae128cb`. It matches exactly, including the three attachment IDs and investigation mode. This rules out attachment loss during frontend navigation for this incident.

| Original attachment ID | Actual uploaded name | Stored SHA-256 |
| --- | --- | --- |
| `40151834153e4b6c82baa080ebad7ce5` | Blue Centrifugal Pump Assembly.png | `8424d9cacc6581d926b2c4b2f57904aa5d8113ec565cd6722cd04c7fd9ba5ef8` |
| `83f78cfe9d5d4084b15b9a84f121c8f9` | PUMP-017_maintenance_report.pdf | `326d9190b3b655f5199445b25f9f31b55f88abe842e3cce2dbc769cf2903e356` |
| `274073ca87664ad7b53b4dc411033666` | PUMP-017_sensor_trend.csv | `a65fd18017f20c7b0f486492ceba6cbb2a5c984cec7dca7eacb02d80644d4d6e` |

The actual image name was **Blue Centrifugal Pump Assembly.png**, rather than the intended `PUMP-017_inspection.png` cited in the PDF. Ingestion normalized the actual image to JPEG and recorded its original-input SHA-256 separately. The stored image was intact. PDF extraction produced three genuine text chunks; its cross-reference warning was not the failure.

## Pipeline assessment and correction

| Stage | Original / reproduced finding | Correction and verification |
| --- | --- | --- |
| Frontend submission / attachment persistence | Three HTTP uploads, saved IDs and exact request hash prove all files reached the right conversation/job | Three-file receipt sequencing and existing composer lifecycle regression retained; no phrase-specific frontend workaround |
| Durable job creation | 202 accepted and actual job persisted | New jobs also retain their effective request snapshot, including question/context and IDs, so failures before message creation remain inspectable |
| Requested asset context | PUMP-017 was present in the question; old presentation derived identity only from a completed report | Requested identity is projected/preserved separately and labeled user-provided/unverified; source-declared metadata is not promoted to independent verification |
| RUL guard | Negated coordinated exclusion was treated as an affirmative RUL request | Clause-aware affirmative request detection; actual RUL requests still require compatible prediction inputs; negated NASA commands do not load models |
| CSV ingestion / profiling | File contained24 rows/10 columns, but four header variants were absent from the industrial mapping; old metadata recognized only72 channel records | Added explicit unit-bearing vibration, discharge/suction pressure and speed aliases; now168 source records across7 channels, with no NASA model transfer |
| Quality flags | Original quality labels were `OK`; old good-only filter would reject every profile window after the routing fix | Configured `OK`→`good` normalization with original `source_quality` retained; bad/unknown labels remain excluded; old policy reproduced `insufficient_measurements` |
| Document / image specialists | Original run never reached them | Real local retrieval/vision exercised; three PDF excerpts and four model-derived image observations retained in final browser run |
| Proposal context / citations | First repaired replay exposed only E1–E3; raw proposal cited absent E4–E6 in prose, correctly rejected | Bounded question excerpts, balanced modality context, query-ordered measurement channels and explicit requested-asset provenance; typed support/conflict aliases remain constrained to actual sources |
| Proposal generation bounds | Intermediate candidate changes failed token and schema validation and were withheld | Investigation output cap1200; bounded JSON-safe prose patterns keep free-text citations out of generated prose and keep schema limits effective. Explicit known bare references are restored; unknown references still fail. No invalid output is silently trimmed or filled in |
| Availability verification | First browser success incorrectly claimed CSV quantitative data was unavailable despite actual stored rows | Added deterministic correction of that narrow generic absence claim against actual asset-scoped inventory; missing channels/other assets remain unknown |
| Failure UI and lifecycle | Error became the summary and could enable speech; asset/source context was absent | Actual sanitized error code/stage appears in a failure panel; error text is not an analysis/speech summary; submitted files and valid partial evidence remain inspectable; worker exceptions are terminal and sanitized |

The first intermediate bracket-pattern attempt was rejected during verification; raw local HTTP reproduction showed schema-bound violations. It was replaced with bounded JSON-safe patterns. Those failures are retained rather than reported as passes. Strict canonical/alias validation and evidence membership checks remain enabled.

## Actual acceptance

- Exact production-stored three-file replay: job `4e64cd224abb49ec9429c55aa9855f3a`, **complete**, 13.437279s elapsed by the local HTTP harness. Its image result was an explicitly recorded reuse of the same actual QA vision inference; it was not a fabricated observation.
- Fresh browser submission: job `2c99d53fe4aa4244b63f0bad5746a223`, saved report `333db52fcf2242c98f3cf1f61a3abc50`, conversation `e68b47ad23b34468bc084a60bd61731e`; **complete**, 31.750s actual backend elapsed. Browser wall-clock/TTFT was not instrumented and is not inferred from this number.
- Final submitted IDs: `a29c53d04a7e4ba687dacbf738bc480c`, `b1abc8a97476433f91215f9927b07585`, `10fdde19f99246e7a3e7f77eef5c4289`. Actual request, stored attachment ownership and report association were checked, not inferred from chips.
- All7 measurement groups were independently recomputed from original CSV bytes; all24 values, source quality labels and timezone-aware timestamps per group matched source snapshots. PDF observations include the OPEN work order and reported dampness. Image observations resolve as `model_generated`, `human_verified=false`.
- Two proposed mechanisms remain **tentative, low support**. Supporting IDs resolve to real supplied records; missing checks are retained. There are **0** returned contradiction references: none were invented or treated as confirmed falsification. Causal meaning remains subject to engineering review.
- All16 report source references resolved; numeric source support was checked independently, not just ID formatting. Browser citation navigation opened the actual CSV preview/original. The real execution trace opened and its terminal state is complete. No prediction tool ran and no synthetic pump telemetry was sent to a C-MAPSS model.

| Channel | Readings | First24 mean | Last6 mean | Difference | Source-declared unit |
| --- | --- | --- | --- | --- | --- |
| bearing_temp | 24 | 64.254167 | 73.316667 | 9.0625 | degC |
| current | 24 | 11.370833 | 11.733333 | 0.3625 | A |
| downstream_pressure | 24 | 4.80875 | 4.69 | -0.11875 | bar |
| flow | 24 | 46.833333 | 44.466667 | -2.3666667 | m3/h |
| speed | 24 | 1479.9583 | 1480 | 0.041666667 | rpm |
| upstream_pressure | 24 | 1.7879167 | 1.7883333 | 0.00041666667 | bar |
| vibration | 24 | 3.23875 | 4.585 | 1.34625 | mm/s RMS |

Displayed figures above use8 significant digits; exact values/rows/windows are in the private acceptance JSON. The first24 window covers the entire24-sample file; last6 overlaps it. These are descriptive statistics, not a separately established healthy baseline. CSV coverage is2026-11-17 08:00–13:45UTC; the PDF's maintenance/inspection times remain document claims. No unified incident cutoff or independently verified image capture time was invented.

## Commands and final output

| Command | Actual final result |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest -q` | 370 passed, 1 warning, 158.32s |
| `npm --prefix web test` | 26 passed, 0 failed, 7479.47ms |
| `npm --prefix web run build` | TypeScript passes; normal Vite build14.24s |
| `python -m ruff check app tests scripts` | All checks passed |
| `python -m black --check app tests scripts` |206 files unchanged |
| `python -m pip check` | No broken requirements found |
| Private real replay / acceptance verifier | Exact request hash,3 file associations,7 independent profiles, PDF/image provenance, sources, hypotheses and traces verified |
| Private preservation/restart checks |813 native hashes,7956 frozen files,3 original source bytes and15 production tables unchanged; served bytes and loaded source identity verified |

The existing Starlette/AnyIO deprecation and Vite >500kB chunk advisory remain. No environment update, model training, calibration, download, protected deletion, Git publication or public deployment occurred. QA8001 is stopped; only the normal local app and Ollama remain.

## Files and reproducibility

Changed application logic: `app/orchestration/planner.py`, `app/chat/service.py`, `app/evidence/measurements.py`, `app/evidence/context.py`, `app/evidence/inventory.py`, `app/investigation/proposal_schema.py`, `app/investigation/schemas.py`, `app/investigation/jobs.py`, `app/api/frontend.py`, `app/api/main.py`, `config/app.yaml`, `web/src/services/api.ts`, `web/src/types/api.ts`, `web/src/pages/InvestigationWorkspace.tsx`.

Permanent regressions: `tests/unit/test_pump_investigation_regression.py`, `tests/unit/test_evidence_context.py`, `web/tests/frontend-integration.test.mjs`; the prior actual React/router pending-upload regression remains enabled. Cases cover negation/affirmative guards, non-C-MAPSS investigation, aliases/quality/statistics, context selection, strict citations, missing/wrong-conversation files, worker exceptions, failure projection, three-file intake and guarded availability correction.

Private proof is `.runtime/pump_failure_20261119_025319/`, located by `.runtime/pump_failure_current.txt`. It retains original record/source/trace, consistent production backups, request signature proof, failed and successful replays, raw local proposal inputs/outputs, final acceptance, browser snapshots, `pump-success.jpg`, tests, protection and restart receipts. Do not publish the database, uploaded files or raw prompts. Public measured summary: `PUMP_017_INVESTIGATION_RESULTS.json`.

## Explicit remaining acceptance limit

The original pre-normalization PNG bytes were not retained by the old ingestion path and were not found in the bounded local search. The exact application-stored image was used for stored-source replay and as the fresh browser upload input; PDF/CSV bytes are exact. **A byte-for-byte fresh upload of the original PNG remains unverified**, pending its local path (already requested). The original upload's recorded hash remains preserved. Do not describe the normalized-image rerun as verification of that unavailable original PNG.

This fixes the reproduced release-blocking routing/data-flow failure. It does not establish physical fault truth, image authenticity, calibrated causal probabilities or universal diagnostic accuracy. To use the fixed normal application, start a **new investigation** with the intended files; refreshing the preserved historical failed job does not rerun it.

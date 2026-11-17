# V3.2 local implementation handoff

The requested nine phases were implemented incrementally against the working V3 application. The result is a local investigation workspace connecting real tools to the existing chat, with actual optional speech/video processing and evidence-linked uploaded-case exports. **Full browser/hardware acceptance and broad semantic/physical diagnostic validity remain incomplete.** The user-visible prototype is not a validated machine-failure diagnosis system.

## 1. What changed

`app/orchestration/workspace.py`, expanded typed tool adapters and `config/intelligence.yaml` connect ordinary scoped questions to trends, maintenance, dependencies, differential investigations, memory, fleet, interventions and reports. Independent cheap reads run concurrently; dependent/heavy work stays serial. Actual outputs, source IDs, errors, model provenance and timings persist in existing conversation metadata. Simple chat avoids incident tools. Explicit source context prevents guessing which plant/incident is intended.

`web/src/features/workspace` and existing chat components expose those capabilities through a collapsible sidebar and contextual inspector. Existing `/engineer`, `/predictions` and other V2/V3 routes remain. Selected uploads and native predictions join the same conversation. Historical facility analysis and later uploaded observations are explicitly separate. Sensor values/units/gaps, source snapshots, hypothesis comparisons, retrospective cases, model choices, trace and report links now have real backing operations.

`app/media`, `app/voice`, ingestion and `Voice.tsx` add bounded local Whisper/Kokoro recordings and reply audio; OpenCV samples actual video frames. Optional packages/weights are isolated, pinned and loaded only when requested. Explicit CSV/JSON measurements have validated schema and exact row provenance. `scripts/setup_media.py`, requirements-media.lock.txt and MEDIA_PROVENANCE.md document reproducible optional setup and licence decisions. The quarantined unused PyAV GPL codec build is not on the application path.

`app/investigation/identity.py`, engine/schema changes and short model-facing evidence aliases provide dynamic candidate counts, conservative merging, stable IDs, parent-preserving revisions, source-group weighting, measured falsification, explicit ambiguity, novelty stopping and budgets. `app/reports/evidence_case.py` exports actual uploaded-evidence cases separately from simulated facility reports. Unknown source aliases are withheld; original source records remain exact and resolvable.

## 2. Commands and actual verification

Final full suite: **198 passed, 2 warnings, 139.21s** (`.runtime/v3_2_final_tests.log`). Ruff and Black pass for all 117 Python files; TypeScript/Vite pass, **639 modules / 9.53s**, with a 776.10 kB JS chunk advisory. The warnings remain Starlette/AnyIO deprecation and joblib physical-core fallback. Baseline was 155 passed/117.63s; an intermediate full checkpoint was 190 passed/149.90s. The first final regression had 197 passes and one new test assertion failure: PNG input is correctly normalized to stored JPEG; the assertion was corrected to check actual stored MIME, then the full suite passed. Both logs remain. Commands: `python -m pytest tests -q -p no:cacheprovider`, `python -m ruff check app scripts tests`, `python -m black --check app scripts tests`, `npm run build -- --outDir dist-v3`, `python scripts/verify_parity.py` and actual loopback API/model demonstrations. Exact history is in V3_2_PROGRESS.md and docs/V3_2_*.json.

| Actual live check | Measured result |
| --- | --- |
| Ordinary Qwen chat | PASS; 21.389999999999418s |
| Four FD default predictions plus two-model comparison | PASS; 54.125s; actual CPU native results retained |
| Historical prefixes/investigation/what-if/memory/PDF | PASS; 3.2809999999954016s |
| Generated recording → ASR → same-chat Qwen → reply WAV | PASS; 146.04699999999866s; reply excerpt was 600 characters in this probe; current UI explicitly requests 250 |
| Video with corrected descriptive routing | PASS; 239.65600000000268s; actual decoding and three VLM calls, no hypothesis call |
| Final photo investigation and actual saved-case PDF | PASS; 86.10900000000402s; **fresh Qwen hypotheses with exact prior VLM extraction reused**; three low-support tentative mechanisms |
| Fresh note-answer citation restoration | PASS; 21.25s; accurate absence of supplied maintenance facts and exact source citation |
| PDF render/visual review | All 11 pages reviewed: uploaded case 4 pages/8966 bytes; facility 7 pages/13762 bytes |

The photo demo first failed because only one compound candidate was returned, then failed with the old generic invalid-structured-response error. Both failures are retained in V3_2_LIVE_INITIAL.json and V3_2_LIVE_SECOND.json. The old error did not prove timeout; later code distinguishes it precisely. Compact aliases and more concise guidance produced the accepted targeted rerun, saved as V3_2_LIVE_PHOTO_FINAL.json. This is a set of actual checks across revisions, not one all-passing uninterrupted batch or an accuracy/latency benchmark. Video demonstration input was transparently encoded from a licensed still, not a real failure recording.

## 3. Model and data preservation

All **813** original protected native artifact/preprocessing hashes match. V3.2 freshly executed the four FD default pathways and two-model comparison. The earlier complete **168-route** CPU and **44-reference** audit remains preserved; verify_parity validates its metadata, not fresh inference. No retraining, calibration, Optuna resume or scientific-data edits occurred. The disclosed legacy autoencoder archival-CSV mismatch at 1e-4 remains historical; the independently executed exact original/consolidated CPU reference was 44.62064057588577 cycles on both sides. No tolerances were widened.

Original user state stays in `.runtime/v2`; QA/demo state is separate in `.runtime/v3_2_qa` and was never imported. A fresh consistent SQLite backup and exact table-content digests verified **all 13 existing tables unchanged** after cutover: six conversations, 40 messages, five attachments, four chunks, four V2 cases, three predictions, two V3 cases, 59 evidence/source records each, one V3 report and four V3 runs (plus schema/review tables). The user's additional history since V3 was preserved. Proof: V3_2_CUTOVER_STATE.json. Pre-V3.2 source/SQLite backups live in `.runtime/v3_2_backups`; previous served V3 frontend is `output/v3_frontend_before_v3_2_20261117T150751`. Earlier V2 frontend, source/bundle snapshots and protected external archives/environment remain. V2 and V3 ZIP hashes still match exactly (V3_2_PRESERVED_BUNDLES.json); V3.2 uses a separate ignored private ZIP. Git reset/clean/staging/commit/push and permanent research deletion were not performed.

## 4. Entry points and operation

V3.2 is running at http://127.0.0.1:8000 (hidden launcher PID 38044, actual uvicorn PID 43976; wrapper PID 35744). QA 8001 is stopped. Restart with `.\scripts\dev.ps1` or `python scripts/dev.py`; verify process identity before stopping anything. Use V3_2_RUNBOOK.md for demos/recovery. OpenAPI version is **3.2.0**; V2 contract_version **2.0** remains compatible. Actual served routes/assets match the final build; ten scenarios and ML/text/vision/ASR/TTS/video readiness passed (V3_2_CUTOVER_VERIFICATION.json). The launcher starts only already installed local Ollama, seeds missing simulated state and performs no software/model downloads. Optional readiness: `python scripts/setup_media.py --verify-only`; full explicit provisioning and probes are separately documented.

Root `.venv` still resolves third-party libraries through the protected external `.pth` environment. Do not remove it. Source and artifact relocation checks use that existing dependency environment; clean installs, offline completeness and macOS/Linux execution are not established. The runtime bundle excludes personal state, environments, Node modules, Ollama/media weights and scenario/truth databases; it is a private source/native-assets bundle, not an offline installer.

## 5. Remaining limits and blockers

Supported browser access host is unavailable. No control bypass, alternate unsafe URL flow or fabricated screenshot was used. Desktop/mobile layouts, keyboard/focus/accessibility, interactive upload/replay/inspector actions and microphone/speaker hardware need manual acceptance using the runbook. API/content/build tests do not prove these interactions.

Intent routing is conservative rather than unrestricted semantic planning. Retrieval is lexical; case similarity is provisional canonical overlap, and the UI explicitly labels retrospective memory. General hypothesis deduplication does not solve arbitrary semantic equivalence. Model source references and weights can be valid while the proposed causal relationship is weak or wrong. Dynamic model counts allow abstention, and actual photo candidates remain tentative/low support. Neither model confidence nor industrial diagnosis/prevention accuracy is calibrated. Facility rules and generator remain jointly designed toy simulation; their historical evaluation is not physical evidence.

Speech is English only and slow on CPU; ASR whole-recording bounds are not word timestamps. Unsupported non-English reply text is refused; unknown lexicon words are spelled out. Video has a strict small sampling budget, no audio-track transcription and no real-motion benchmark. User measurement asset/unit association is unverified. Local endpoints assume a trusted single-user machine; no public/multi-user security claim or equipment actuation is made. The Vite chunk-size advisory and the documented dependency warnings remain.

## 6. Next work requiring different evidence

Complete the manual browser/microphone/speaker checklist when the supported browser host is available, then collect independently measured, properly associated industrial evidence for an evaluation designed separately from the generator/rules. A later Figma redesign can reuse the clean feature boundaries. No new research training, public deployment, paid service or protected-file deletion is authorized by this handoff.


## 7. Final private package and relocation proof

`output/sire_v3_2_local_runtime.zip` contains **1052 files / 140260908 bytes**; SHA-256 `7137fd98e6ee6fd38a8d7adebc513cdca0d3a2b2e16ede147d6a0a479017093a`. Its per-file manifest is adjacent; CRC and every entry hash passed. V2/V3 bundles are unchanged. The ZIP captures the verified source/native-assets checkpoint before post-export proof was appended to working docs. It excludes personal state, environments, Node modules and provider/media weights.

Actual extracted execution passed all 813 native hashes, FD004 LightGBM **32.158785034361294 cycles**, a 33-source simulated investigation, a reproducible **14188-byte PDF** and current case/scenario/OpenAPI contracts. Absent optional media returned explicit 503, as intended. See V3_2_RELOCATION_VERIFICATION.json. This used existing protected third-party dependencies and does not establish a fresh machine install. Remaining acceptance is listed above; no implementation permission is needed for the user to use the running local app.

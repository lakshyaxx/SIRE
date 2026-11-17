# SIRE V3 capability matrix

Evidence is current-session execution unless explicitly labeled historical. The project is a local prototype; browser/mobile and voice/video acceptance are incomplete.

| Capability | Status | Verified behavior / limitation |
| --- | --- | --- |
| V2 persistence and native predictions | verified | Final suite 155 passed/86.32s. Exact pre/post cutover comparison preserved all original 4 conversations, 36 messages, 5 attachments, 4 chunks, 3 V2 cases and 3 predictions. |
| Protected model files | verified | All 813 hashes match. Fresh V3 CPU audit: 168 ready, zero unavailable; 44 frozen independent V1-reference comparisons passed. Archive source was not rerun in V3. |
| Typed orchestrator / operational trace | verified | Whitelisted adapters, typed inputs, deadlines, intra-run dedup, cancellation, hashed arguments. Real normal chat and explicit NASA command trace executed. |
| Freeform autonomous tool planning | partial | Conservative modality routing and explicit NASA commands; scenario/asset/replay actions use structured UI/API scope. No arbitrary LLM tool execution or general open-world planner. |
| Canonical evidence ledger | verified | Append-only source/evidence rows, hash validation, original private uploads and exact locators; V2 document, prediction, user and persisted visual/schema claim aliases resolve without rewriting legacy IDs; visual claims remain model-generated. |
| JSON/CSV/DOCX/XLSX/PDF/text/images | verified parsers | Office ZIP/XML bounds, no macro/formula execution, original hashes, paragraph/sheet/row/page references. Generic uploaded data does not become a compatible RUL dataset automatically. |
| Synthetic facility and hidden truth | verified | Ten trials, six assets, directed timestamped relations, deterministic hourly telemetry, gaps and logs. Truth is in a separate evaluator-only SQLite file; reader denies truth/ATTACH/writes. |
| Time fencing / replay | backend verified | Both observed_at and available_at checked; prefix-only baseline and statistics. Memory checks case creation availability. What-if output is fenced too. |
| Differential investigation | verified within toy catalogue | Nine extensible canonical rule mechanisms, two-stage graph/evidence expansion, support/conflicts/missing tests, multiple contributors and abstention. General semantic expansion/merging beyond this catalogue remains partial. |
| Engineer workspace | build/API verified | Scenario/asset selection, raw charts, replay/playback, chronology, actual directed dependency SVG and exact relation list, hypotheses, evidence/trace drilldown. Browser interaction and responsive accessibility review blocked. |
| Case memory / human review | verified subset | Persisted revisions, canonical mechanism overlap and separate unverified human notes. No embedding model or semantic case-search accuracy benchmark. |
| Fleet indicators | verified | Latest timestamps, quality/missing samples and unit-aware trend indicators; no universal failure probability or physical alarm control. |
| Early warning / scenario evaluation | verified synthetic only | 20 trials on seeds 42/43: top-1 12/16, top-3 16/16 labeled incidents, 588/588 citations, normal false warnings 0/2, ambiguous abstention 2/2. Not real-plant/LLM efficacy. |
| Synthetic what-if | verified | Same seed/noise, bounded service_hour/load_factor assumptions, real recomputation and prefix comparison. Uploaded real machinery unsupported. |
| Markdown/PDF reports | verified | Actual stored snapshots, source/report integrity, genuine downloads, deterministic PDF bytes; rendered QA. Human review remains an assertion, never physical truth. |
| Actual local text / vision | verified examples | Qwen text and VL instruct tags executed; bearing observations differ from a blue-image negative control. Final qualitative NASA reply completed in 22.187s under the numeric guard. Original unsupported-confidence failure retained; no general diagnosis/citation-entailment benchmark. |
| ASR / TTS / video frames | blocked | No configured verified local speech models or FFmpeg/video adapter; optional isolated metadata lookup stalled and was stopped without installation. PCM metadata works; voice routes return clear 503, no fake transcript/audio or hosted fallback. |
| Cross-platform / fresh install | partial | pathlib and Python launcher provided; current Windows environment tested. Root venv still uses protected external third-party packages. Fresh network install and other OSes unverified. |
| Public deployment / equipment actions | not performed | No public listener/tunnel, paid API, control-system integration, research deletion or model retraining. |

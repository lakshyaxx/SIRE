# SIRE V3 verified local implementation checkpoint

The 20-page directive was read completely. Gates 0-8 were executed in order, with safe alternatives and explicit incomplete acceptance where runtime or tooling was unavailable. The working core now serves locally at http://127.0.0.1:8000. This is a prototype checkpoint, not a validated physical diagnostic system or a claim that every directive feature is complete. Milestone history: [V3_PROGRESS.md](V3_PROGRESS.md). Capability-by-capability status: [V3_CAPABILITY_MATRIX.md](V3_CAPABILITY_MATRIX.md).

## 1. Implemented flows and code

| Flow | Working implementation |
| --- | --- |
| Existing V2 chat, images, documents and NASA predictions | Preserved `app/chat`, `app/ingestion`, `app/prediction`, `app/storage`, and existing frontend routes. Explicit `Predict FD003 engine 42` runs real saved inference before local Qwen commentary. Numeric facts are independent of generated prose; `app/prediction/narrative.py` rejects specified unsupported claims. |
| Typed orchestration and actual execution traces | `app/orchestration/runtime.py`, `tools.py`, `planner.py`: whitelisted typed dispatch, call/time budgets, cancellation, intra-run deduplication, actual timings, argument hashes and persisted traces. General conversational routing is conservative; unrestricted freeform autonomous planning is incomplete. |
| Exact evidence and provenance | `app/evidence/ledger.py`: immutable source/evidence snapshots, five source classes, hashes, information-availability times and exact resolver. Legacy document/prediction/user/visual/schema IDs resolve without rewriting V2 history. Visual statements remain model interpretations. |
| Simulated facility and replay | `app/simulation/settings.py`, `generator.py`, `repository.py`, `config/simulation.yaml`: ten seeded trials, six assets, 28 channels, timestamped dependencies, gaps/quality flags and available event logs. Reader enforces observed and available cutoffs; evaluator truth lives in a separate database denied to the investigator. |
| Differential investigation | `app/temporal/analytics.py`, `app/investigation/facility.py`: prefix-only summaries, actual raw-row citations, bounded graph/evidence expansion, nine canonical mechanisms, support/conflict/missing checks, several contributors and abstention. Ordering scores are not causal probabilities. Open-world semantic expansion is incomplete. |
| Engineer UI | `web/src/features/engineer/Engineer.tsx`, `AssetGraph.tsx`: scenario/asset selection, actual sensor chart, replay presets/playback, chronology, directed dependencies, hypothesis/evidence/trace drilldown, cancellation, human notes, memory, fleet, what-if and genuine report links. TypeScript/build/API checked; browser acceptance remains open. |
| Case memory and fleet | `app/knowledge/case_memory.py`, `app/assets/fleet.py`: versioned provisional cases, historical creation/availability fences, explained canonical overlap/differences, separate unverified review notes and actual quality/trend summaries. No embeddings or confirmed physical-case learning. |
| Explicit interventions and reports | `app/simulation/what_if.py`, `app/reports/engineering.py`: same-seed synthetic service/load changes, fenced trajectories, baseline-version verification, frozen source/report metadata and genuine reproducible Markdown/PDF downloads. Motor load/current changes are shown on the affected asset; no real-world causal validity claimed. |
| Additional files and honest modality failures | `app/evidence/formats.py`, `intake.py`, V2 ingestion extensions: bounded JSON/CSV/DOCX/XLSX plus existing PDF/text/images, original hashes and locators, local quotas and no macro/formula execution. `app/voice/capabilities.py` validates bounded PCM structure; unavailable ASR/TTS/video returns explicit errors. |
| Additive API and reproducible tools | `app/api/intelligence.py`, `scripts/seed_scenarios.py`, `evaluate_scenarios.py`, `verify_v3.py`/`.ps1`, `demo_smoke.py`, `dev.py`, `export_runtime.py`. Existing V2 routes/contracts retained. |

## 2. Commands and observed tests

| Executed check | Actual output |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider` | **155 passed, 2 warnings, 86.32s**; `.runtime/v3_final_tests.log` |
| `python -m ruff check app scripts tests` | All checks passed |
| `python -m black --check app scripts tests` | 96 files unchanged |
| `npm run build -- --outDir dist-v3` in `web` | TypeScript passed; Vite 635 modules, 7.84s; 739.69 kB JS chunk advisory |
| `python scripts/audit_models.py` followed by `--missing --output <temporary path>` recovery | Fresh actual CPU inference **168 ready / 0 unavailable**; 813 native hashes and 44 comparisons to independently executed frozen V1 references passed. Original archive source was not rerun in V3. |
| `python scripts/verify_parity.py` | Current 813 hashes and 168/44 recorded verification entries passed; this fast command does not perform fresh inference |
| `python scripts/demo_smoke.py` against isolated QA | Actual text 55.312s, image 68.829s, all four FD defaults, replay/case/what-if/evidence/report downloads; `V3_LIVE_SMOKE.json` |
| Actual final qualitative NASA request against current QA | Qwen `qwen3:4b-instruct`, FD003 engine 42, 114.49630975928234 cycles; complete in 22.187s, source facts plus guarded qualitative caveats; `V3_FINAL_LIVE.json` |
| Distinct actual vision input | Qwen `qwen3-vl:2b-instruct` described the blue control as no component, unlike licensed bearing observations; `V3_VISION_NEGATIVE_CONTROL.json` |
| Final genuine report download/render | 7 pages, 13,704 bytes; repeated bytes identical. First/hypothesis/last rendered pages reviewed. PDF SHA `e7d46891f34a816e43b9040eee80b45a98ecc2a00d4937231abcc77eebb3dba9`; `output/v3/final_report.pdf` |
| Local V3 cutover HTTP check | `/`, `/engineer`, `/predictions`, `/docs`, `/api/v1/cases` and both built assets 200; ten scenarios; ML/text/vision ready; `V3_CUTOVER_VERIFICATION.json` |

All four live default predictions used NASA simulation histories: FD001 115.3478990753549, FD002 11.592229512416276, FD003 51.46118890357053 and FD004 25.05196696607433 operating cycles. They refer to the tested default engine histories, distinct from the explicit FD003 engine 42 example. The original unsupported “95% confidence interval” narration is retained as a quality failure in `V3_NASA_CHAT_LIVE.json`; a subsequent unsafe commentary was visibly withheld. The final qualitative-only subtask passed the guard. These examples do not establish a general unsupported-claim rate or physical diagnostic accuracy.

The two final test warnings are Starlette/AnyIO alias deprecation and joblib physical-core detection falling back to logical cores. Restricted esbuild parent reads initially failed; the ordinary approved build passed. OneDrive derived audit metadata writing failed after 113 saved successes; missing routes were resumed outside OneDrive and complete metadata published atomically. No inference output was substituted. A QA probe initially called a nonexistent message subroute; the corrected existing conversation endpoint passed.

## 3. Synthetic evaluation

`python scripts/evaluate_scenarios.py` ran **20 trials**, seeds 42/43. Only the offline evaluator reads hidden assignments; investigation reads the separate observable database. Results: top-1 **12/16**, top-3 **16/16** labeled incidents; citations **588/588** valid; normal false warnings **0/2**; ambiguous abstention **2/2**. Mean case latency 0.5406500000004598s, p95 0.625799999999981s, zero timeouts. Per-case lead hours and baseline-threshold comparisons were computed on six coarse prefixes and retained in `.runtime/v3_evaluation/results.json` and [EVALUATION_REPORT.md](EVALUATION_REPORT.md). Several toy cases first warned 24 or 36 hours before the assigned reference, while controls/ambiguous cases had no lead time.

Generator and rules were designed together. These are integration results on toy histories, not an independent plant dataset, LLM efficacy study, calibrated alarm benchmark or measurement of real failure prevention.

## 4. Data safety

No retraining, Optuna resume, recalibration, source research deletion, paid API, public deployment, equipment command or Git reset/clean/staging/commit/push occurred. Existing Git changes remain: the large prior V2 retirement appears as deleted tracked paths; V3 did not remove that research. `V3_GIT_STATE.json` records aggregate status without exposing private file contents.

All **813** protected artifact hashes match. Pre-V3 source ZIP and consistent SQLite backup are in `.runtime/v3_backups`; a second SQLite backup was made at cutover. Exact post-start comparison preserved **4 conversations, 36 messages, 5 attachments, 4 chunks, 3 V2 cases and 3 predictions** unchanged. Only additive V3 tables/schema version 3 were introduced. The former served frontend is intact at `output/v2_frontend_before_v3_20261117`. The original V2 runtime ZIP SHA remains `18c9bb7c20af2ca43cf470d9594c72313a129011304521c07ca90bd50b5f3f24`. External snapshot/research/environment paths in `V3_BASELINE_AUDIT.md` remain protected.

V3 is exported separately as `output/sire_v3_local_runtime.zip` with its manifest. It includes private native inference assets and is for private distribution. It excludes personal state/imports, environments, model-provider weights, Node modules, generated scenario/truth databases and internal truth mapping; generator source remains. It is not a standalone offline installer. Final packaging proof is appended to `V3_PROGRESS.md`.

## 5. Local launch

Run **`.\scripts\dev.ps1`** from the repository, or `.venv/Scripts/python.exe scripts/dev.py`. Open **http://127.0.0.1:8000**, **/engineer** and **/docs**. The verified V3 production service is left running; the isolated QA server is stopped at teardown. The launcher seeds only missing synthetic state and starts an already installed local Ollama when needed. It never downloads models on startup.

Installed instruct tags are `qwen3:4b-instruct` and `qwen3-vl:2b-instruct`. Configuration is `config/app.yaml` / `config/simulation.yaml`; supported environment overrides are in [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md). V2 `contract_version` remains 2.0 for compatibility; additive OpenAPI app version is 3.0.0. Root `.venv` **still depends on the protected external preserved third-party environment** through its `.pth`; keep that directory. Current Windows execution was tested; fresh installs and other operating systems were not.

## 6. Manual UI acceptance still required

Supported browser host was unavailable; earlier native URL-policy validation also blocked control. No bypass or fabricated screenshots. HTTP and builds do not establish browser QA. Follow [SHOWCASE_RUNBOOK.md](SHOWCASE_RUNBOOK.md):

- Desktop and 375px layout, sidebar/deep links, keyboard focus, Enter/Shift+Enter and composer scrolling.
- Upload success/error/partial batches; actual source links; restart history; streamed Stop and error states.
- Scenario/asset selection, plot units/gaps, replay presets/playback, dependency graph, evidence drilldown and investigation cancellation.
- Saved review notes, prior-case differences, what-if trajectories and actual downloaded Markdown/PDF contents.
- Missing provider/model behavior, camera/file picker; microphone permission/transcript review/playback only after a real speech runtime is verified.

## 7. Blockers and limits

ASR/TTS/video remain unavailable: no verified speech model/runtime or bounded video adapter. An optional isolated permissive speech dependency metadata lookup stalled and was stopped without installation or model download. Typing and still-image ingestion are the working alternatives. No transcript or audio success is claimed.

Browser/mobile/camera/microphone acceptance remains unverified. The nine-rule catalogue, conservative planner, lexical document retrieval and canonical overlap memory remain partial relative to semantic multi-domain planning/learning. Generic uploaded histories are parsed as evidence but do not become calibrated physical diagnostics or NASA-compatible predictions automatically. No causal probability or guaranteed prevention is provided. Multilingual PDF text is escaped in the PDF fallback rather than claiming full-font coverage; Markdown preserves original Unicode. Long local text/vision latency, limited free RAM and a frontend chunk advisory remain. The app is loopback single-user with no multi-user authentication; do not publish it as-is.

The historical legacy autoencoder archival CSV tolerance failure at 1e-4 (maximum 0.0017175758857703727 cycles) remains disclosed, despite exact original/consolidated CPU output matching in the recorded worst-case pair. No tolerance was widened to hide this difference.

## 8. Next three actions

1. Complete and record the manual browser/mobile five-moment walkthrough, fixing observed usability defects before calling this showcase-ready.
2. Provision and genuinely test bounded local speech (and then optional video), with isolated pinned permissive dependencies, verified model hashes, resource limits and user-reviewed transcripts.
3. Build independent uploaded-asset evaluation and broader semantic planning/retrieval against held-out incident evidence, with citation/claim checks and explicit abstention; preserve all existing NASA models and split safeguards.

No new user decision is required to run the verified core. Additional protected-environment replacement or public deployment remains outside this checkpoint.

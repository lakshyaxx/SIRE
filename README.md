# Current release fix — SIRE4.8.1

The reproduced pump investigation failure is repaired and SIRE is running on http://127.0.0.1:8000. Final regression:370 backend tests,26 frontend tests; normal build/Ruff/Black/pip passed. All813 native files,7956 frozen files and15 production tables remain unchanged. Exact stored-source replay and fresh browser rerun passed; original pre-normalization PNG reupload remains unverified because those bytes were unavailable. Details and precise limits: [pump release report](docs/PUMP_017_INVESTIGATION_FIX.md). The original failed job remains an unchanged historical record; submit a new investigation to run the fixed code.

Prior checkpoint below is retained as historical evidence.

---

# Current application checkpoint — 2026-11-19

SIRE **4.8.0** now serves the integrated Figma interface locally at **http://127.0.0.1:8000** using the existing backend, models, history and normal launcher. Start `.\scripts\dev.ps1` from this repository (or `.venv/Scripts/python.exe scripts/dev.py`). The canonical frontend is `web/`; the old delivered export is recoverably archived, not required to run the app.

Verified: **346 backend tests**, **24 frontend tests**, **24 real network cases**, **12 selected FD001–FD004 native routes** and **7 offline-process checks** passed. Final audits match all **813 native hashes**, **7,956 frozen files** and **15 production tables** exactly, including after restart. Actual browser chat/upload/investigation/source/trace/PDF, prediction/comparison, cancel/restart and responsive checks passed within their documented scopes.

Physical microphone/speaker/autoplay/barge-in and broad diagnostic semantic validity remain unverified. Generated auxiliary strings can truncate, and CPU speech/deep inference remains slower than greetings. This is a local prototype, not a qualified industrial diagnosis system. No training, model downloads, public deployment or Git publication occurred.

Read [final integration](docs/FINAL_FRONTEND_INTEGRATION.md), [measured verification](docs/FRONTEND_TEST_RESULTS.md), [machine-readable results](docs/FRONTEND_INTEGRATION_RESULTS.json) and [readiness and remaining acceptance](docs/FINAL_APPLICATION_READINESS.md). Older V3.2/V3/V2 checkpoints below are historical.

---

# SIRE V3.2 investigation workspace

V3.2 is running locally at **http://127.0.0.1:8000**. It connects incident context, sensor history/replay, evidence and competing hypotheses, retrospective case memory, fleet/what-if, actual NASA model comparison, execution traces and real PDF/Markdown exports to the existing chat. Local English speech and bounded audio/video ingestion are implemented with isolated open-source workers.

Final verification: **198 tests passed / 139.21s**, two documented dependency warnings; Ruff/Black and TypeScript/Vite passed. All **813** protected native hashes match. Actual Qwen, four FD defaults/comparison, photo/document hypotheses, recorded-file speech round trip, sampled-frame vision and historical/report paths were exercised. All existing database tables survived cutover exactly. Browser/mobile and physical microphone/speaker interaction remain **unverified**; source-valid model claims can still be weak or wrong. This is a local prototype, not a validated industrial diagnostic system.

Start `.\scripts\dev.ps1`; keep the protected external Python environment. Read [current handoff](docs/V3_2_HANDOFF_REPORT.md), [progress and actual checks](docs/V3_2_PROGRESS.md), [capability status](docs/V3_2_CAPABILITY_MATRIX.md), [A/B/C runbook](docs/V3_2_RUNBOOK.md) and [optional media provenance/setup](docs/MEDIA_PROVENANCE.md). `python scripts/demo_v3_2.py --base http://127.0.0.1:8000` runs actual demonstrations serially and retains failures. `python scripts/export_runtime.py` now creates the separate private **V3.2** bundle; old V2/V3 bundles remain unchanged. No training/tuning, protected research deletion, paid service or public deployment occurred.

The following V3/V2 sections are historical checkpoints; current V3.2 guidance above supersedes their old voice/video, process and export status.

---

# SIRE V3 industrial intelligence

V3 extends the working V2 app with typed tool planning, an immutable evidence ledger, a deterministic simulated facility, historical replay, evidence-linked differential investigations, case memory/review notes, fleet indicators, same-seed what-if and Markdown/PDF reports. New code is verified incrementally; the current gate, exact tests and blockers are in [V3 progress](docs/V3_PROGRESS.md) and [capability matrix](docs/V3_CAPABILITY_MATRIX.md).

Launch: `.\scripts\dev.ps1`; open **http://127.0.0.1:8000** and **/engineer**. The launcher idempotently creates only missing synthetic scenario data. Verified V3 now serves on port 8000 with the original V2 history; cutover proof is in docs/V3_CUTOVER_VERIFICATION.json. Keep the protected external Python environment. [Deployment guide](docs/DEPLOYMENT_GUIDE.md), [data dictionary](docs/DATA_DICTIONARY.md), [method](docs/INVESTIGATION_METHOD.md), [model provenance](docs/MODEL_PROVENANCE.md) and [actual synthetic evaluation](docs/EVALUATION_REPORT.md) describe the practical limits.

Run `.\scripts\verify_v3.ps1` for tests/lint/format/staged build; `--full-model-audit` additionally executes every native route. `python scripts/demo_smoke.py --base http://127.0.0.1:8000` calls real providers and tools. `python scripts/evaluate_scenarios.py` runs the offline truth-isolated toy benchmark. `python scripts/export_runtime.py` creates the separate private V3 bundle and preserves the V2 ZIP.

Source labels remain distinct: NASA simulation, SIRE synthetic scenarios, real uploads, manual claims and model interpretations. The scenario engine never passes plant-pump telemetry to NASA RUL models. Model explanations are tentative; source-backed numeric cards and narration guards prevent unsupported confidence/interval claims from becoming completed prediction answers. General semantic claim entailment is not proven.

Local ASR/TTS/video generation and browser/mobile interaction QA are blocked by current runtime/tool availability. No public deployment, paid API, research deletion, training or tuning occurred. The older V2 instructions below remain useful context; current V3 commands/status take precedence for the active application.

---

# SIRE local investigation app

SIRE opens into persistent chat. Ask ordinary questions, attach images or PDF/TXT/MD/CSV evidence, and request competing engineering explanations. The separate Predictions screen runs original saved NASA C-MAPSS models for FD001–FD004. Photos cannot produce RUL. Saved sensor predictions join chat through an explicit result ID.

Start this installed workspace in PowerShell:

```powershell
.\scripts\dev.ps1
```

Open **http://127.0.0.1:8000**. API docs: **http://127.0.0.1:8000/docs**. Ctrl+C stops the launcher. It starts an already installed local Ollama when needed and never downloads software. Configured tags: `qwen3:4b-instruct` and `qwen3-vl:2b-instruct`. No hosted fallback is enabled.

Root `.venv` currently reuses third-party packages through a `.pth` pointing to `C:/Users/laksh/SIRE_SAFETY_BACKUPS/v2_retired_20261117/environment/Lib/site-packages`. **Keep that preserved environment** until a clean replacement is installed and checked. Application source and ML artifacts do not import retired phase folders.

For a fresh Windows environment, restore private `ml/artifacts` files and registry from the checksummed runtime bundle, install Python 3.11 and Node 22.12+, then run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-runtime.lock.txt
cd web
npm ci
npm run build
cd ..
.\scripts\dev.ps1
```

The full lock includes the PyTorch CUDA wheel index; actual serving was verified on CPU. A fresh network install and macOS/Linux install were not executed. Other platforms can use `python scripts/dev.py` with compatible dependencies; the captured Windows lock may need platform-specific wheel changes. A Git source clone lacks private weights/data. The bundle excludes Python/Node environments, Ollama weights and private chat state.

| Path | Purpose |
| --- | --- |
| `app/` | API, chat, prediction, knowledge, providers, evidence engine and SQLite |
| `web/` | React/TypeScript chat-first UI and replaceable CSS tokens |
| `ml/registry/catalog.json` | One application catalog: 168 native inference routes |
| `ml/artifacts/cmapss/` | Native loaders, weights, preprocessing and sensor histories; Git ignored |
| `data/` | Licensed demo image and project model card |
| `tests/` | Unit, integration and preserved C-MAPSS regressions |
| `docs/` | Proof, contracts, migration and manual review |

Verification and private export:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m ruff check app scripts tests
.\.venv\Scripts\python.exe -m black --check app scripts tests
.\.venv\Scripts\python.exe scripts/verify_parity.py
# Slower: fresh CPU inference for every route
.\.venv\Scripts\python.exe scripts/audit_models.py
# App must be running; these call real local models
.\.venv\Scripts\python.exe scripts/smoke_transport.py
.\.venv\Scripts\python.exe scripts/smoke_v2.py
.\.venv\Scripts\python.exe scripts/export_runtime.py
```

Read [build status](docs/BUILD_STATUS.md), [test evidence](docs/TEST_EVIDENCE.md), [manual review](docs/SHOWCASE_RUNBOOK.md), [model coverage](docs/MODEL_CATALOG.md), [API contracts](docs/API_CONTRACTS.md), [deployment](docs/DEPLOYMENT.md) and [preservation/rollback](docs/CLEANUP_MANIFEST.md).

Old phase trees and V1 app are reversibly relocated to the verified external archive. No permanent research deletion, retraining, Optuna resume, Git publication or public deployment occurred. Browser/mobile interaction and visual accessibility review remain unverified. Small-model explanations are tentative, without a fault-diagnosis accuracy benchmark. N-CMAPSS and voice are outside this prototype.

# Local Stress Lab reproduction

This assesses the existing V3 stack as implemented in SIRE API3.2.0. It uses the separate synthetic public facility corpus and disposable state. It does not replace research, fit models or import industrial telemetry into NASA predictors. See [findings](STRESS_TEST_FINDINGS.md) for measured outcomes and open gaps.

## Inputs, environment and boundaries

Use the existing root Python3.11 `.venv`, protected external third-party environment and installed local Ollama/media models. No dependency installation was required for this assessment. Root requirements/configuration remain the source of pinned dependencies. Source, Ollama/media weight hashes and environment availability must be checked when reproducing on another machine; fresh installation and cross-platform runtime acceptance have not been demonstrated.

The public root used here is `C:/Users/laksh/OneDrive/Desktop/SIRE_STRESS_LAB_PUBLIC_INPUTS/SIRE_STRESS_LAB_PUBLIC`. Public manifest, README, TEST_RUNBOOK, schemas and matrix must pass audit before any intake. An evaluator_only directory in the input root causes refusal. A separate private evaluator archive must remain outside every app/repository/input/retrieval root. Do not open or copy labels into this adapter or an agent prompt. Public adversarial content is untrusted fixture data.

The adapter maps original asset types/IDs and twelve named measurement columns with explicit units into the real observable schema. Original SQLite telemetry row IDs, source fields and SHA remain in snapshots. An incident loads a 48-hour prior window plus24-hour following window, and the actual repository cutoff fences all queries. Following-window storage is not permission to use future rows. Fleet-only queries use a24-hour latest window. No pretrained model is fitted or recalibrated.

Telemetry/event timestamp availability is an explicit assumption because the corpus lacks independent ingestion clocks. Combined work-order completion content is available only at closed_at; lab-analysis rows with unknown result availability are excluded. Static graph validity is assumed. These assumptions are logged in mapping_policy.json and do not prove physical information availability.

## Actual interfaces

| Fixture capability | Actual SIRE interface / trace |
| --- | --- |
| Conversations and chat | POST /api/v1/conversations; POST /api/v1/chat/message (SSE); GET /api/v1/conversations/{id} |
| Context/history/hypotheses | Typed context scenario_id/asset_id/as_of/case_id; actual temporal.summary, events.timeline, assets.relations, facility.investigate |
| Peer comparison | fleet.overview with typed peer_asset_id; same registered asset_type; actual values/units/source IDs |
| Generic files/image/speech/video | POST /api/v1/attachments; persisted parser/media metadata; actual knowledge.retrieve, vision.inspect, audio.transcript and local frame extraction |
| Evidence and trace | GET /api/v1/evidence/{id}; GET /api/v1/runs/{id}/trace; immutable exact source snapshots |
| NASA inference | POST /api/v1/predictions/run; exact dataset/model and existing genuine engine001 saved history; separate preserved legacy RUL autoencoder alias |
| Reports/counterfactuals | Typed case report/download; simulations/what-if explicitly rejects unsupported external generators |

The fixture's mode=engineering is not blindly translated into forced Investigate mode. Its natural prompt selects real tools; missed routing is recorded. Expected abstract tool names are mapped in tests/stress_lab_config.yaml, with absent mappings left unknown. A successful upload does not assert that vision, ASR, OCR or retrieval ran.

## Reproduce in a new disposable namespace

Run from the repository root in PowerShell. Pick a **new** namespace; the names below are examples and must not overwrite saved assessment outputs. The runner refuses existing results without --resume. Resume skips already recorded cases, including failures; it never silently selects a successful retry.

```powershell
$stressCorpus = 'C:/Users/laksh/OneDrive/Desktop/SIRE_STRESS_LAB_PUBLIC_INPUTS/SIRE_STRESS_LAB_PUBLIC'
$stressState = '.runtime/stress_lab/new_run'
.\.venv\Scripts\python.exe tests/stress_lab_adapter.py --corpus $stressCorpus --state $stressState --priority P0 --audit-only
.\.venv\Scripts\python.exe tests/stress_lab_adapter.py --corpus $stressCorpus --state $stressState --priority P0
.\.venv\Scripts\python.exe tests/stress_lab_adapter.py --corpus $stressCorpus --state $stressState --priority P1
.\.venv\Scripts\python.exe tests/stress_lab_adapter.py --corpus $stressCorpus --state $stressState --priority P2
.\.venv\Scripts\python.exe -m scripts.stress_lab.consolidate --corpus $stressCorpus --state $stressState
```

The policy runs serially, bounds expensive cases and limits load concurrency to2. Each priority must have every case recorded or explicitly unrun before the next begins. P2 concurrency4/8/16 remains outside this bounded run. No background shared provider is stopped. Actual source hashes at start and per-case status/latency/errors are saved.

After the first freeze, finish only previously budget-unrun P0/P1 cases in a separate namespace:

```powershell
$stressContinuation = '.runtime/stress_lab/new_completion'
.\.venv\Scripts\python.exe -m scripts.stress_lab.completion --corpus $stressCorpus --parent $stressState --state $stressContinuation
.\.venv\Scripts\python.exe -m scripts.stress_lab.consolidate --corpus $stressCorpus --state $stressState --completion $stressContinuation
.\.venv\Scripts\python.exe -m scripts.stress_lab.saved_audit --corpus $stressCorpus --state $stressState --continuation $stressContinuation --answers .runtime/stress_lab/new_run/assessment_answers.jsonl --output .runtime/stress_lab/new_saved_audit
```

The continuation validates the original frozen SHA, uses fresh case memory, and runs the remaining P0 cases before remaining P1 cases at concurrency1. Combined answers preserve original unrun records inline. Executed failures cannot be replaced. saved_audit opens existing SQLite databases read-only, recovers actual persisted replies/model spans/load-session traces and checks additional EV snapshots without running a model or rewriting answers. Unknown legacy aliases remain unreviewed; it does not create compatibility evidence on a read.

For one P0 smoke subset use --ids followed by actual test IDs from the matrix, in a different state directory. A partial inventory is not a final freeze. --intermediate produces derived aggregates without claiming completion. Tests/schemas/matrix and invalid/adversarial directories are not bulk-indexed into retrieval.

## Output interpretation

The completed run lives under `.runtime/stress_lab/full`, its top-up under `completion`, recovered saved output under `saved_audit`. Original phase rows, frozen first-pass rows, combined first executions and derived grades are distinct artifacts. `trace_path` leads to actual responses, SSE events, API timings, tool steps and model provenance. `fixture_ids` carries original file hashes. Recovered saved_outputs.jsonl links all actual assistant messages and persisted traces, including multi-turn/load cases whose initial flattened citation/model lists were incomplete. Native-only/rejected cases retain real API responses and are not given invented assistant text.

`frozen_answers.jsonl` / frozen_answers.json seal the original phase records. `assessment_answers.jsonl` / assessment_answers.json seal the original executed rows plus first executions of previously unrun cases. Repeated consolidation validates exact UTF-8 bytes and preserves seal timestamps. Derived grades can correct a documented harness classification but never replace original answers. Retested fixes live in separate namespaces such as smoke_after, peer_after, history_after, cancel_after, network_final and full/tts_after.

Automated snapshot support checks compare exact saved numeric/event payloads with original public records; they do not establish what a generated answer's causal claim means. The separate manual review is a purposive selected-claim audit, not a random sample. Future-evidence results apply to mapped timestamps under the availability assumptions. Latency is whole-case wall time and includes conversion/upload/source validation. Memory is sampled harness working set, not total Ollama/worker/VRAM demand. Do not convert these metrics into physical diagnostic confidence.

The optional jsonschema package is absent in the current environment, so full suggested-contract validation is unverified. Actual API/Pydantic contracts and adapter required-field/status regressions run. The supplied public grader is a presence/self-report check only; on Windows it needs UTF-8 mode:

```powershell
.\.venv\Scripts\python.exe -X utf8 C:/Users/laksh/OneDrive/Desktop/SIRE_STRESS_LAB_PUBLIC_INPUTS/SIRE_STRESS_LAB_PUBLIC/scripts/grade_results.py .runtime/stress_lab/full/evaluation_adapter_results.jsonl
```

## Independent private evaluation

Top1/top3 and false-positive rates remain null until the actual external evaluator package is available. The separate `scripts/stress_lab/offline_evaluator.py` uses only the standard library and imports no SIRE/provider/ingestion module. It requires an unchanged answer SHA and an external evaluator-approved cause mapping/label contract, with approved multi-cause and control policies. Do not infer aliases from symptom text or public severity and do not prepare a purported approved mapping yourself. The original label schema is not assumed; an actual approved conversion is required before use.

Only after an external evaluator supplies the paths and approval, run the offline command with its --answers, --frozen, --labels, --contract and --output arguments. Both private paths must be outside the repository. The evaluator emits aggregate/split counts only, with no labels, per-incident correctness or canaries. Never send the private inputs or grading details back to the diagnostic engine or use them to tune holdout behavior. No real private evaluation has been performed for this checkpoint.

## Verification and current operational state

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app scripts tests
.\.venv\Scripts\python.exe -m black --check app scripts tests
npm.cmd --prefix web run typecheck
```

Final source: **229 passed /2 warnings /165.45s**, Ruff clean, Black **138 files unchanged**, TypeScript typecheck passed. Logs: `.runtime/stress_lab/final_source_tests.log`, final_ruff.log, final_black.log and frontend_typecheck.log. The warnings are existing Starlette/AnyIO deprecation and joblib physical-core discovery. Unit tests with explicitly test-only fixtures/provider delays verify invariants and are separate from real-corpus/API/model benchmarks; their results are not substituted for engine accuracy.

Production remains healthy at127.0.0.1:8000 with its previous loaded code and unchanged state. Source fixes are tested locally but not loaded into that existing process. Native813 hashes and all13 production logical table digests match preflight. Old V2/V3/V3.2 private bundles and external environment remain intact. No package publication/export, dependency installation, retraining or research deletion occurred. Owned QA8002 is stopped. Browser/mobile/microphone/speaker acceptance remains unverified; the supported browser host is unavailable. Any normal main-app restart should happen outside an active user turn, using the repository's existing launcher.

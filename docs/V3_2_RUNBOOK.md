# SIRE V3.2 local operation and demonstrations

## Start and inspect

Run `.\scripts\dev.ps1` from this repository, or `.\.venv\Scripts\python.exe scripts/dev.py`. Open **http://127.0.0.1:8000**. The launcher serves only loopback, seeds missing clearly simulated scenarios and uses the already installed Ollama. It never downloads software or weights on startup. `/docs` exposes API schemas; `/engineer` and `/predictions` preserve the dedicated V3/V2 routes.

The current root environment depends on the protected external environment named in V3_BASELINE_AUDIT.md. Keep it intact. Fresh machine dependency installation is documented separately in DEPLOYMENT_GUIDE.md; that is not a claim of a tested clean install. Optional speech/video setup and licensing are in MEDIA_PROVENANCE.md. Check `/api/v1/health` and `/api/v1/voice/capabilities` before a demonstration. Text uses `qwen3:4b-instruct`; vision uses `qwen3-vl:2b-instruct`.

The main chat has conversation history, attachment selection and a contextual inspector. Choose an incident/asset and information cutoff to use simulated facility tools. Without that scope, ordinary conversation or uploaded-evidence analysis stays separate. Uploads are not silently treated as historical observations in the selected simulated facility. Inspect Evidence, Hypotheses, Sensors & replay, Case memory, What-if & fleet, Models & RUL, Trace and Reports as needed. Follow the actual trace/error status; a successful HTTP response alone does not establish a completed investigation.

## Demo A: actual NASA predictions

Open Models & RUL or `/predictions`. Select FD001, FD002, FD003 or FD004, an available engine history and a native model. Run it and inspect RUL **operating cycles**, artifact/preprocessing provenance and CPU runtime. Compare two compatible models, then attach the selected prediction to the existing conversation. An ordinary request such as `Predict FD003 engine 42` also runs a native prediction before commentary. NASA histories are simulated turbofan data; a component photograph is not that engine and cannot supply RUL inputs.

Expected output is the actual stored inference result plus model/hash provenance, never a hard-coded prediction. V3.2 live checks exercised all four FD defaults and a two-model comparison; the complete 168-route inference audit is the preserved V3 audit, not a fresh V3.2 sweep.

## Demo B: uploaded evidence and tentative mechanisms

Start a new chat. Upload `data/demo/bearing_cc0.jpg` (licence/source are adjacent in the demo data) and an actual maintenance note, or a note explicitly declaring which information is unavailable. State symptoms truthfully as measured, reported or hypothetical. A reproducible sample request is: `Investigate the attached licensed demonstration photograph. Hypothetically the operator reports intermittent bearing noise under load; that is a simulated user claim, not a measured incident. Compare plausible mechanisms and missing discriminating measurements. Cite only actual supplied evidence.`

Use investigation mode if needed. Inspect the actual image interpretation, retrieved note, source classes, tentative mechanisms, conflicts, missing inspections and model trace. A photo alone cannot establish internal wear or physical cause. Revisit after attaching new measurements; parent cases remain unchanged. Ask `Export this investigation report as PDF` after a completed saved case. The report freezes the actual evidence and case, rather than generating a new diagnosis.

The model may abstain or fail its deadline/schema checks; the application retains the real failure and never invents an alternative result. Exact successes and failed attempts are recorded in V3_2_PROGRESS.md and the live-results files. CPU/model swapping can make multimodal requests slow. Avoid concurrent demonstration jobs.

## Demo C: simulated historical reconstruction

Select Trial 01 and its target asset in the chat context. Choose T−48h, T−24h and T−12h in turn. Ask `Show sensor trends and maintenance records`. Inspect timestamped readings, units, gaps and when each record became available. Then ask `Investigate this fault, compare competing hypotheses and export an engineering PDF report`. Open Hypotheses, Evidence and Trace; inspect competing mechanisms, contradictory/missing evidence and real source pointers. The investigator cannot read the separately stored evaluator truth.

Open Sensors & replay to change the cutoff and inspect recorded chronology/dependencies. Ask `What if we service at hour 48?` to compare explicit same-seed simulated trajectories. These interventions are toy simulated outcomes, not real-world prevention claims. Ask `Find similar prior cases` to inspect provisional retrospective comparisons; they are not proof available at the historical cutoff. Download the actual frozen PDF/Markdown from Reports.

## Speech, audio, video and measurement evidence

Record a question starts capture only after explicit browser microphone permission. Stop & transcribe locally retains the WAV and fills the existing editable composer. Review the transcript and press Send. Generate reply audio explicitly, then play, mute, stop or cancel. The full conversation remains in the same history. Physical microphone/speaker interaction needs manual verification; file-based speech round-trip checks are recorded separately.

Upload supported audio or bounded video through the same attachment control. Original recordings, source hashes, decoded frame indices and actual decoder timestamps are retained; use selected child frames as evidence if desired. Inspect media errors rather than assuming a failed extraction succeeded. Video audio transcription is not implemented. A licensed-still video demonstrates decoding/vision routing only.

Industrial CSV/JSON must explicitly provide `asset_id,timestamp,channel,value,unit`; timestamps need a timezone, values must be finite, each asset/channel/time must be unique and a channel's units consistent. Summaries expose exact rows and declared units. The equipment association/unit truth is user supplied and unverified. Arbitrary sensor uploads are never fed into C-MAPSS models. Existing bounded TXT/Markdown/PDF/DOCX/XLSX/JSON/CSV/image parsers remain available; no macros or formulas are executed.

## Reproduce automated checks and recover

Run `python -m pytest tests -q -p no:cacheprovider`, `python -m ruff check app scripts tests`, `python -m black --check app scripts tests`; in `web`, run `npm run build`. Native runtime checks: `python scripts/verify_parity.py` verifies hashes and recorded audit metadata without retraining. `python scripts/demo_v3_2.py --base http://127.0.0.1:8000` executes actual demonstrations serially, creates clearly labeled demo conversations and saves raw successes/failures in `output/v3_2/<UTC timestamp>`. `--only` selects individual documented checks. `--reuse-photo-evidence` reuses prior actual source extraction but generates hypotheses fresh; this is not a fresh VLM inference. No live request uses canned output.

Stop cancels the current chat; an interrupted response remains visibly partial/cancelled. If a local model is missing, inspect the named error and installed Ollama tags; do not download another model implicitly. If media hashes differ, preserve the files and review the mismatch. For a frozen worker, use the API cancellation control and wait for cleanup/deadline before starting another job. Restart only the owned local SIRE server. Do not terminate unrelated Python processes.

For UI acceptance, manually check desktop and a 375px layout, sidebar/inspector focus, keyboard Enter/Shift+Enter, upload selection/child frames, replay plots/cutoffs, report links, Stop/retry and microphone/audio controls. Build/API verification does not substitute for these checks. Backups and private bundles stay separate for V2, V3 and V3.2; never reset the database or replace it with QA/demo state to recover the UI.

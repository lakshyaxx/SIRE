# V4 actual verification

Scope: local HTTP/client contracts and installed services. Browser picker, microphone, audible playback, mobile and keyboard acceptance remain unverified. Browser host was unavailable; native input returned `coordinate input geometry is unavailable`. No screenshots or physical-device passes are claimed.

## Reproduce safely

Use root `.venv`; preserve its external third-party environment. Production is `http://127.0.0.1:8000`. All fixtures/tests below used separate `.runtime/v4/qa` at8001. Never point the acceptance scripts at production. No evaluator labels are mounted or read.

```powershell
$env:SIRE_STATE_DIR=Join-Path (Get-Location) '.runtime/v4/qa'
$env:SIRE_WEB_BUILD='dist-v3'
.\.venv\Scripts\python.exe -m uvicorn qa_server:create_qa_app --factory --app-dir .runtime/v4 --host 127.0.0.1 --port 8001
```

`qa_server.py` is the ignored test factory calling `create_app(state_dir=STATE, probe_model=False)`. To create another isolated QA state, change the state directory and retain the factory. Build with `npm run build -- --outDir dist-v3` from web/. Use a fresh output directory for every run:

```powershell
node scripts/v4_upload_e2e.mjs http://127.0.0.1:8001 <PUBLIC_CORPUS_ROOT> .runtime/v4/new_upload_run repair
.\.venv\Scripts\python.exe scripts/v4_acceptance.py --proof .runtime/v4/new_upload_run/verification.json --output .runtime/v4/new_acceptance --prediction --media
```

The first script transpiles the actual frontend api.ts and invokes its real multipart/SSE transport under Node. It does not drive a browser DOM. The second uses actual HTTP, saved source IDs, genuine compatible NASA samples and real audio bytes. Its per-check failures are saved; inspect results.json, not just process exit status. The committed regression fixtures are explicitly test-only; production does not select them as provider fallbacks.

## What ran

| Path | Actual result / proof under `.runtime/v4/` |
|---|---|
| Picker/camera | Real JSX handler live-FileList regression failed2 before repair; both pass afterward. Browser dialog selection pending. |
| PNG/PDF/CSV/DOCX/XLSX | Five ready durable intake receipts, original hashes and canonical source IDs in upload_e2e_reserved_context/verification.json. |
| Single image | Real Qwen VLM and chat response in upload_e2e_ready; schematic identified as synthetic, no hidden measurement established. |
| Document use | http_acceptance_verified: PDF/DOCX/XLSX exact quoted passages and source locators all supported_contextually; no LLM on the exact-retrieval route. PDF served inline with actual PDF bytes. |
| CSV | Actual normalized units, original row/field identities,11channels,44 independently recomputed claim checks. Deterministic response0.854s in reserved-context run; never routed to NASA. |
| Combined image/manual/CSV | combined_final: complete175.594s, two real proposal rounds, saved case and genuine PDF/Markdown. Vision explicitly cached from same bytes/question/model digest. Execution success does not establish semantic correctness. |
| Bad files | Empty413; invalid image, malformed CSV width, invalid PDF and unsupported executable422. |
| Retry/isolation/cleanup | Backend tests cover same-conversation dedup, cross-conversation separation and failed SQL cleanup. Client cancel aborts and warns that already stored files can remain. Interrupted native browser uploads/reload not independently exercised. |
| Speech | Real vendor WAV6.625s -> Whisper -> same-chat response -> Kokoro WAV267040frames/24000Hz/11.126667s. Pipeline83.391s. ASR transcript unverified, no industrial transcription accuracy claim. |
| Inline player | Actual controller requests speech then calls audio.play;7frontend contracts include stop/cancel IDs, pause/resume and text sanitation, with explicit test-only audio transport. This is not heard playback. |
| Video | video_probe: actual3-frame decoding with decoder timestamps; initial wrong adapter endpoint405 retained; corrected intelligence/execute first-frame VLM200/40.719s. Other frames/full video chat not rerun. |
| FD001–004 | Genuine saved ENGINE-001 histories, actual default native models; all4 targeted HTTP predictions pass. No168-route campaign rerun. |
| History/peers | engineering_check: actual deterministic temporal.summary/events.timeline/fleet.overview,6347rows through08:00, all within cutoff. No LLM claimed. |
| Exact negative control | engineering_claim_corrected: original telemetry:row:901 / PUMP-001 / vibration /03:00:4.907 contradicted,2.685 verified_exact. Earlier adapter selected PUMP-004 and was corrected against the actual pointer schema; original output retained. |
| What-if | External corpus returns422 external_simulation_unsupported; no built-in trajectory substituted. |
| Cancellation/outage/injection | Full regression preserves prior socket/disconnect/cancel, untrusted-document, unit/domain and isolated unreachable-loopback checks. Shared Ollama was never stopped. No new real-UI failure campaign claimed. |
| Runtime persistence | Main app restarted from scripts/dev.py; source fingerprint and frontend match current build, startup ML probe ready,13production tables unchanged after restart. QA saved conversation reload and durable sources verified. |

## Correctness limits and sampled review

The actual image visibly says `SIRE SYNTHETIC INSPECTION REFERENCE`, `ASSET PUMP-005 / CORROSION`, and `SIMULATED DRAWING: not a photograph or physical diagnosis`. The earlier image answer's label, oval and brown circles are visually supported; a claim about fluid composition/internal corrosion is an interpretation, not a physical observation.

The combined answer still has semantic defects: its unresolved list says flow/suction-related measurements and ambient temperature delta are absent, while the supplied PUMP-001 profiles include flow, upstream_pressure and ambient_temp. Their sufficiency for cavitation is unverified, but absence should not be asserted. Candidate links also relied on an unlinked PUMP-005 image/PUMP-001 CSV; the ranking exclusion is fixed and recomputation retained in association_rerank.json, without altering the original answer. Generated missing-test/unresolved prose still needs human verification. No population entailment, causal accuracy or private top-1/top-3 score is claimed.

Report PDF validation:147pages/756382extracted characters. It contains full snapshots and is too verbose for a concise showcase; visual layout was not independently rendered/reviewed. Original export remains unchanged.

## Test gate

`python -m pytest -q`:246passed,2dependency warnings,199.53s. The final free-text-citation-alias change followed that full run;22relevant hypothesis tests passed1.36s, including the new regression. Ruff clean; Black145files clean; TypeScript and frontend production build pass;7frontend tests pass. Logs and cutover_verification.json are retained. No frozen stress result was relabeled or rerun.

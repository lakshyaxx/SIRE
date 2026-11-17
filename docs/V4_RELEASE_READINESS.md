# V4 local readiness

**Conditional local demo; not V4 complete.** The patched application is running at http://127.0.0.1:8000. API4.0.0 retains contract2.0. Loaded source/config/frontend fingerprint matches current files; ML startup inference is ready. Shared Ollama PID29972 stayed running. Detailed actual results:V4_E2E_VERIFICATION.md; measured limits:V4_LATENCY_REPORT.md; milestone record:V4_PROGRESS.md; machine map:V4_CAPABILITY_MATRIX.json.

| Scenario | Decision |
|---|---|
| Exact CSV statistics / source inspection |Backend/client route verified. Good local demo candidate, pending actual picker acceptance. |
| PDF/DOCX/XLSX passage retrieval |Backend verified, exact quotations/locators; guidance does not prove incident cause. |
| Genuine NASA FD001–FD004 |4default saved-sample routes verified; keep dataset/operating-cycle caveats. |
| Combined image/manual/CSV |Real case/report execution passed;175.594s with vision cache. Human review required; missing-evidence prose and source association remain material limits. |
| Inline voice / recording |Code and real server audio chain verified; physical microphone, permission, audible autoplay/pause/resume/stop and barge-in acceptance pending.83.391s is not fluid conversation. |
| Video |Real3-frame extraction and first-frame VLM verified; complete multi-frame chat/manual playback not rerun. |
| General physical diagnosis |No-go for verified physical-cause claims. Source IDs and model agreement are not physical confirmation. |
| Public deployment / portability |Not authorized or performed. Current .venv still relies on preserved external packages. No clean-environment claim. |

## Start and demonstrate

Already running. For a future restart from the repository:

```powershell
.\scripts\dev.ps1
```

1. New chat: attach a compatible structured CSV, wait for ready, ask `Summarize the exact descriptive statistics and units`. Inspect original rows/charts/citations. Generic industrial CSV must remain ineligible for NASA.
2. Attach a maintenance PDF and ask `According to this document, quote the actual inspection record passages`. Open its page/source; verify exact passage and source authenticity caveat. A combined investigation can then include an image and CSV, with explicit unlinked-asset limits and longer latency.
3. Enable Talk to SIRE, tap Record, grant microphone permission deliberately, stop, review/edit transcript, Send. Speak answer uses the inline player; exercise pause/resume/stop and another recording to interrupt. **Human validation required**; no permission bypass or always-on recording.

For synthetic fixtures use the isolated QA8001 app, never production. Existing saved production conversations were not used for test data. If the user had the page open during cutover, reload once for the new frontend.

## Checkpoint / recovery

`.runtime/v4/backups/` retains pre-V4 source ZIP, consistent production database snapshots, and frontend_before_cutover. No destructive migration or cleanup. Old frontend assets remain in web/dist alongside the new indexed assets. Production was deliberately restarted only after regression/preservation checks; original launcher stopped without its child tree before app replacement so shared Ollama survived. New actual web-server PID48524/tool session59221. Avoid a broad process-tree kill that stops shared inference.

After restart all13production tables exactly equal the preflight database backup. All813native files and7956frozen stress files verified before cutover; original V2/V3/V3.2 ZIP hashes match their recorded values. No retraining, evaluator access, research deletion, dependency replacement, paid service or public publishing occurred. Original2792Git deletion records were inherited; no new research deletion performed.

## Prioritized remaining work

1. Human browser acceptance: actual picker/drag-drop, upload cancellation/retry/reload, citation navigation and desktop/mobile keyboard controls. Native automation input is blocked.
2. Semantic missing-evidence checks: the completed model answer incorrectly described available flow/ambient channels as missing. Keep mechanisms, requested checks and unlinked asset relationships unverified; source entailment remains incomplete.
3. Conversation latency and physical voice acceptance. No more long model runs were started after the user's speed request.
4. Short report summaries with separately accessible complete snapshots; current populated export147pages is unwieldy and visually unverified.
5. Additional bounded video/codec and clean portable-environment acceptance. Preserve existing environment and trained artifacts while doing so.

Private diagnostic top-1/top-3, population false-positive rates and general qualitative entailment accuracy remain unestablished. Historical frozen544executed/563inventoried results retain their previous classifications.

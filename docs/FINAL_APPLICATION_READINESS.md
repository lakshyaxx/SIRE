# Current local release —4.8.1

The reproduced pump investigation failure is repaired and SIRE is running on http://127.0.0.1:8000. Final regression:370 backend tests,26 frontend tests; normal build/Ruff/Black/pip passed. All813 native files,7956 frozen files and15 production tables remain unchanged. Exact stored-source replay and fresh browser rerun passed; original pre-normalization PNG reupload remains unverified because those bytes were unavailable. Details and precise limits: [pump release report](PUMP_017_INVESTIGATION_FIX.md). The original failed job remains an unchanged historical record; submit a new investigation to run the fixed code.

Prior checkpoint below is retained as historical evidence.

---

# Local application readiness — 2026-11-19

**Integrated build served and verified on http://127.0.0.1:8000.** This is a local engineering prototype with explicit acceptance limits. It is not publicly deployed or industrially qualified.

Use `.\scripts\dev.ps1` from the repository root, or `.venv/Scripts/python.exe scripts/dev.py`. The launcher uses `web/dist/`, the original production state, original protected environment and existing local Ollama installation. For a fresh frontend build: `npm --prefix web ci` then `npm --prefix web run build`. No replacement frontend folder or model download is required. Default loopback binding remains127.0.0.1.

Verified working paths: persistent text chat and source-backed SIRE description, general Qwen response, real upload→conversation→durable investigation, saved findings/source/trace/PDF, evidence previews, actual native model routing/comparison, scenario what-if, errors/cancel/restart, responsive desktop/phone/tablet layout and local file-based ASR/TTS/video paths. Automatic live voice is implemented using genuine final-utterance capture and local playback but awaits device acceptance.

## Remaining work by priority

| Priority | Remaining acceptance / limitation | Next concrete step |
| --- | --- | --- |
| P1 | Physical live voice, audible autoplay, speaker selection, noise and spoken interruption unverified | User-permitted microphone/speaker browser session; retain actual client/session timings |
| P1 | Small-model causal proposals can be weak; auxiliary output strings can truncate | Evaluate observed claims against exact evidence without truth leakage; preserve failed outputs and improve generation bounds/validation separately |
| P2 | Cold/long CPU speech and deep/native routes remain slower than simple greetings | Use retained per-stage profile; do not infer a browser speedup or download a new model |
| P2 | Main JS still exceeds500kB advisory; broader accessibility/browser/device coverage | Inspect measured loading on target hardware; focused additional splitting only if a measured UI bottleneck warrants it |

No implementation completion claim includes the unverified rows above. There is no need to approve another repository-wide build or repeat previous permissions. The only remaining permission-sensitive acceptance would be physical device access; no recording was silently started.

Rollback is local and recoverable: stop the documented launcher, restore the archived previous frontend source/build and application files using the private checkpoint/patches, then restart. Do not restore an old production database over newer user records. Model weights and research need no rollback because they were never changed. See final integration, test, API, voice, prediction and cleanup reports.

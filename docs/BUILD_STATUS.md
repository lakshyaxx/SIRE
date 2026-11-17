# V3.2 verified local checkpoint - 2026-11-17

Final suite **198 passed, 2 warnings, 139.21s**. Ruff/Black clean (117 Python files); TypeScript/Vite passed (639 modules/9.53s, JS chunk advisory). Current UI/API served on 8000, OpenAPI 3.2.0 / V2 contract 2.0. Ready local text/vision/native models and installed isolated ASR/TTS/video. All 813 native hashes and original V2/V3 ZIP identities intact; every existing SQLite table preserved exactly. Real A/B/C, local speech-file round trip and sampled video checks have exact scopes and retained failures. Browser/mobile/hardware interaction remains unverified. Details: V3_2_HANDOFF_REPORT.md, V3_2_PROGRESS.md, V3_2_VALIDATION_SUMMARY.json, MEDIA_PROVENANCE.md and V3_2_RUNBOOK.md. QA 8001 stopped; production left running.

Earlier build records below are historical; their voice/video availability and process IDs are superseded.

---

# V3 verified local checkpoint - 2026-11-17

V3 core is locally served on 8000. Actual final results: 155 tests passed/86.32s, two documented dependency warnings; Ruff/Black and TypeScript/Vite passed (635 modules/7.84s, chunk-size advisory). Fresh native audit 168 ready/0 unavailable, 813 hashes, 44 frozen-reference comparisons. Original V2 rows preserved exactly after additive migration. Working replay/evidence/hypotheses/memory/what-if/PDF APIs exercised; real Qwen text/vision and all FD datasets exercised. Browser/mobile acceptance and local voice/video remain blocked; semantic planner/memory breadth partial. See V3_HANDOFF_REPORT.md, V3_PROGRESS.md and V3_CAPABILITY_MATRIX.md for evidence and limits. Production remains running; isolated QA is stopped at final teardown.

The following V2 checkpoint is historical provenance.

---

# V2 local build checkpoint — 2026-11-17

Chat-first cutover is implemented. Real Qwen replies, images, document retrieval, saved hypothesis cases, independent FD001–FD004 predictions, explicit result-to-chat linkage, cancellation and restart persistence were exercised. Old phase folders are reversibly retired. No public deployment or permanent research deletion occurred.

| Check | Actual result |
| --- | --- |
| Model routes | 168 INFERRED on CPU, zero unavailable |
| Native integrity | 813 SHA-256 records match |
| Independent primary old/new outputs | 44 within 1e-8 |
| Legacy autoencoder archival CSV comparison | FAIL at 1e-4; maximum difference 0.0017175758857703727 cycles |
| Exact original/consolidated worst-case CPU pair | Both 44.62064057588577 cycles; difference 0.0 |
| Full post-cutover pytest | 116 passed in 159.19s; two warnings |
| Earlier targeted export selection test | 1 passed in 3.08s |
| Ruff / Black / pip check | Pass |
| TypeScript / Vite | Pass; 633 modules, JS chunk advisory |
| Real text / image / document / hypotheses | Completed; V2_LIVE_EVIDENCE.json |
| Actual FD003 linked result + cancellation | 43.38973340387454 cycles; partial text persisted cancelled |
| Restart persistence | 8 messages / 2 attachments retained |
| Browser/mobile/visual accessibility | BLOCKED; manual review steps provided |

Root `.venv` shares third-party packages with the external preserved environment. Keep it. A fresh network install and non-Windows installs are unverified. The private export excludes environments, Ollama weights and personal state; it is not an offline installer.

Generated explanations are tentative, without a diagnosis accuracy benchmark. The live case had two hypotheses, seven actual source IDs and no reliable measured contradiction; no rejection was fabricated. Rule tests use explicit test-only evidence. Bundled knowledge is a project model card, not a mechanical manual. Retrieval is lexical. N-CMAPSS, voice, public/multi-user hosting and calibrated causal probabilities are not implemented.

See TEST_EVIDENCE.md and CLEANUP_MANIFEST.md. V1 checkpoints are historical under docs/history/v1 and the snapshot. QA services stop at final teardown; restart with `.\scripts\dev.ps1`.

Combined live check: V2_MIXED_EVIDENCE.json. Actual compatible FD002 CSV upload and saved ensemble inference returned 11.592229512416276 cycles; cached real vision, exact document passages and all four evidence modalities reached chat. Reply kept photograph and NASA simulation separate. Complete response took 113.65700000000106 seconds.

Private export verified entry CRCs and SHA-256. A candidate bundle was extracted into a different output/relocation_check source location; all 813 hashes passed and a real FD004 LightGBM inference returned 32.158785034361294 cycles there. This proves source/artifact relocation using the current preserved third-party environment, not a fresh dependency install. Extraction proof is output/relocation_verification.json; final bundle/checksum manifest are output/sire_v2_local_runtime.zip and output/sire_v2_local_runtime.manifest.json.

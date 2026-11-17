# V3 final evidence

- Full current-source pytest: 155 passed, 2 warnings, 86.32s (.runtime/v3_final_tests.log).
- Ruff and Black pass; TypeScript/Vite 635 modules/7.84s; large-chunk advisory.
- Fresh native audit: 168 routes, zero unavailable, 813 SHA records, 44 frozen independent comparisons; V3_NATIVE_VERIFICATION.json.
- Real Qwen text/vision and four FD defaults: V3_LIVE_SMOKE.json. Vision negative control: V3_VISION_NEGATIVE_CONTROL.json.
- Prediction explanation defect retained in V3_NASA_CHAT_LIVE.json; safe withheld retry V3_NASA_CHAT_GUARDED.json; current qualitative-only accepted example V3_FINAL_LIVE.json (22.187s).
- Final genuine report: 7 pages/13,704 bytes, repeated PDF SHA e7d46891f34a816e43b9040eee80b45a98ecc2a00d4937231abcc77eebb3dba9, rendered review in output/v3.
- Synthetic N=20 rule benchmark: EVALUATION_REPORT.md. V2 preservation and local startup: V3_PRESERVATION.json / V3_CUTOVER_VERIFICATION.json.
- Browser/mobile/voice/video acceptance blocked or unverified; no screenshot/voice success claim. Fresh dependency installation and non-Windows execution unverified.

Historical V2 evidence follows.

---

# V2 verification evidence — 2026-11-17

Windows, Python 3.11, preserved native dependencies, CPU inference. These checks ran during this build. Root `.venv/Scripts/python.exe` is used after cutover; original/staged checks used the preserved environment before relocation.

| Command / operation | Actual result |
| --- | --- |
| Original model verification before cutover | PASS: 44 actual CPU inferences; ml/registry/v1_reference.json |
| Original C-MAPSS suite before migration | PASS: 56 tests / 28.03s |
| `python scripts/audit_models.py` and repaired `--missing` reruns | PASS: 168 INFERRED / zero unavailable; per-route outputs/latency in verification.json |
| Independent primary old/new parity | PASS: 44 within absolute 1e-8 |
| Migrated legacy tests | Initial FAIL: 54 pass / 2 missing-data failures; exact required source files restored, rerun PASS: 56 / 23.53s |
| Initial V2 tests | PASS: 28 / 44.36s; subsequent guards/regressions added |
| Full post-cutover `python -m pytest tests -q -p no:cacheprovider` | PASS: 116 / 159.19s / 2 warnings |
| Earlier targeted export selection test | PASS: 1 / 3.08s |
| `python -m ruff check app scripts tests` / `python -m black --check app scripts tests` | PASS: 66 formatted Python files |
| `python -m pip check` | PASS: No broken requirements found |
| `npm run build` in web | PASS: TypeScript + Vite / 633 modules / 8.44s; 727.50kB JS chunk advisory |
| `python scripts/verify_parity.py` | PASS: 813 current hashes, 168 recorded inferred routes, 44 non-null comparison objects; does not claim new inference |
| `python scripts/smoke_v2.py http://127.0.0.1:8001` (staged service) | PASS: real local text/image/document/hypothesis responses; content inspected |
| `python scripts/smoke_transport.py` (post-cutover port 8000) | PASS: actual FD003 prediction, explicit artifact in chat evidence, first delta, acknowledged cancel, persisted partial text |
| Root launcher after retirement | PASS: actual ML/text/vision readiness; restart retained 8 messages / 2 attachments; sidebar deep links HTTP 200 |
| Retired-file preservation | 4,218 checked; 4,217 exact, one explained regenerated audit output; no differing trained binary |
| Supported browser | BLOCKED: host unavailable; prior native URL-safety detection also prevented control. No mobile/keyboard/accessibility claim |

Real provider timings from V2_LIVE_EVIDENCE.json:

| Interaction | Elapsed seconds | First actual token seconds |
| --- | ---: | ---: |
| Greeting without asset | 17.686999999999898 | 9.281000000000859 |
| Bearing image + question | 77.29700000000048 | 64.64100000000144 |
| Exact document retrieval | 30.92200000000048 | 18.28099999999904 |
| Two-round hypothesis report | 209.78099999999904 | Structured report event, no fake stream |

The report contains two tentative hypotheses and seven valid evidence IDs. No reliable measured contradiction existed, so conflict lists were allowed empty. Explicit test-only fixtures exercise measured falsification, conflicting/false confident claims, matching/unlinked asset identity, missing/fake references, bounded loops and time budgets. Production never selects test transport output. Unit/integration tests cover corrupted PDF/image/CSV, schema/domain mismatch, provider outages and document injection boundaries. No actual CUDA OOM was reproduced; serving deliberately forces CPU.

Recorded failures/corrections: original LightGBM extra-seed catalog paths initially duplicated a Windows seed folder; metadata fixed and all 12 rerun successfully. Default qwen3:4b thinking response hit its limit; V2_THINKING_TAG_ATTEMPT.json retained, instruct variant selected and rerun successfully. Legacy autoencoder archival CSV tolerance 1e-4 failed with maximum 0.0017175758857703727 cycles; independent exact original/consolidated CPU worst case both returned 44.62064057588577. Failed tolerance remains recorded; no unproven cause asserted. Summary script initially counted null parity fields, failed, was corrected to count actual comparison objects and reran. Local Vite parent-read sandbox denial was resolved by approved filesystem build. An overlong documentation shell command and unsupported delete/add-same-path patch failed before changes; files were then written through short scripts successfully.

Warnings: Starlette's deprecated AnyIO BlockingPortal alias and joblib physical-core detection falling back to logical cores. No failing tests suppressed. Citation IDs establish provenance, not proof of generated causal sentences. Text/vision accuracy and citation entailment are unbenchmarked. Manual interaction checklist: SHOWCASE_RUNBOOK.md. Native mismatch evidence: legacy_rul_parity.json / legacy_cpu_reference.json. Live cancel: V2_TRANSPORT_EVIDENCE.json.

Combined live check: V2_MIXED_EVIDENCE.json. Actual compatible FD002 CSV upload and saved ensemble inference returned 11.592229512416276 cycles; cached real vision, exact document passages and all four evidence modalities reached chat. Reply kept photograph and NASA simulation separate. Complete response took 113.65700000000106 seconds.

Private export verified entry CRCs and SHA-256. A candidate bundle was extracted into a different output/relocation_check source location; all 813 hashes passed and a real FD004 LightGBM inference returned 32.158785034361294 cycles there. This proves source/artifact relocation using the current preserved third-party environment, not a fresh dependency install. Extraction proof is output/relocation_verification.json; final bundle/checksum manifest are output/sire_v2_local_runtime.zip and output/sire_v2_local_runtime.manifest.json.

Final public return-type annotation completion: targeted chat/API checks passed 8 tests, 4 real-prediction tests deliberately deselected, 2.61s; no behavior or model bytes changed. Ruff/Black remain clean. The full 116-test run above preceded this annotation-only edit.

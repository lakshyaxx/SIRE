# Phase 3 artifact and production preservation audit

No protected file was archived, moved, deleted, reset, retrained or published. Original environments and all installed model tags remain. File-level retain-in-place proposals are in [PHASE3_ARCHIVAL_MANIFEST.json](PHASE3_ARCHIVAL_MANIFEST.json); they do not authorize cleanup.

| Protected group | Actual checked count | Outcome |
| --- | --- | --- |
| Native inference files | 813 | Canonical hashes match |
| Frozen stress/research outputs | 7956 | 0 mismatches |
| Original V2/V3/V3.2 bundles | 3 | All hashes match |
| Configured media + embedding assets | 13 | All pinned hashes match |
| Installed Ollama blobs | 20 | All content hashes match; tags unchanged |
| Ollama runtime files | 51 | 33 original + 18 prior CUDA additions unchanged |
| Production tables, immediate cutover | 15 | All 15 exactly equal to consistent pre-cutover snapshot |

## Initial equality failure investigated and resolved

The first comparison against the phase-start production snapshot failed exact equality. Work paused for investigation. Original rows were never changed or deleted; independent live application activity appended records and a completed live job. Added identifiers did not match guarded QA namespace requests. Raw failed receipt, read-only activity audit and qualified resolution are retained, rather than overwritten with an unqualified pass. No database restore or row deletion was attempted.

| Production table | Live added rows since phase baseline |
| --- | --- |
| attachments | 8 |
| cases | 1 |
| conversations | 1 |
| messages | 12 |
| v3_cases | 1 |
| v3_evidence | 47 |
| v3_runs | 7 |
| v3_sources | 46 |
| v45_jobs | 1 |

All original rows remain unchanged. A new consistent `production_precutover.sqlite3` snapshot includes those live additions. Only the verified idle port8000 API was stopped, original local launcher restarted, actual4.7.0 source/frontend/readiness checked, and all 15 tables compared exactly against that immediate snapshot. This verifies the cutover without claiming the whole session's production state was static. Raw SQLite copies stay ignored/private.

## Non-destructive inventory

Actual model manifest entries: 168. Large-file threshold 10000000 bytes; 92 files totaling 12661539845 **logical bytes** across `.runtime`, `ml`, `output`, `data` and `web/dist`. This is not deduplicated physical disk usage; external Ollama blobs were separately hashed. Full inventory stays private to avoid publishing upload paths.

All model proposals remain `retain_in_place`. Nonprimary selection does not establish unused: ensembles, preprocessing and historical reproduction may depend on them. Any future archive needs a transitive dependency audit, separately authorized scope and verified restore at the original paths. No cleanup is needed to use this release. Original `.venv` external `.pth` dependency remains protected.

Local recoverable Phase 2 Git checkpoint: `a635f1055c571e0d5a5bec12afc6439f3be2905c` (61 reviewed application paths, no data/weights), no push. Current Phase 3 changes remain reviewable in the working tree. Baseline and all fresh proof hashes: [results](PHASE3_RESULTS.json).

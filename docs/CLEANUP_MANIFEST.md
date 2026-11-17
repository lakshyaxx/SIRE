# Verified retirement and rollback

No permanent research deletion was performed or proposed. The irreversible deletion set is **empty**. The active root contains no Phase_A–G folders. Unknown content, original research/results/reports, paused studies and V1 source remain preserved outside the active application.

Fresh verified snapshot: `C:/Users/laksh/SIRE_SAFETY_BACKUPS/v2_20261117_000722`: 9,513 files / 3,081,859,612 bytes, every SHA-256 checked. Unchanged files hardlink only to verified prior backup copies, never active working files. Environments, node_modules and caches were excluded; freeze and full Git/working-tree patches preserved. Older snapshot `snapshot_20261116_223519` remains.

Retirement archive: `C:/Users/laksh/SIRE_SAFETY_BACKUPS/v2_retired_20261117`.

| Original active content | Archive |
| --- | --- |
| Phase_A_RUL_Training/.venv | `environment/`, still used for third-party packages by root venv |
| Phase_A–G, engine/backend/frontend/model_store/samples, old output/_archive/migration_staging | `research_and_v1/<original name>/` |
| Superseded root V1 tests | `v1_tests/` |
| Old inventory/verification/package/smoke scripts | `v1_scripts/` |

Exact moves: RETIREMENT_MANIFEST.json and archive retirement_manifest.json. Critical inference map: ml/registry/migration_map.json; current native hashes: catalog.json. Post-move recheck: V2_PRESERVATION_EVIDENCE.json. It checked 4,218 relocated files: 4,217 exact, one explained regenerated V1 verification output. Its original bytes remain in the snapshot; archived latest output exactly matches v1_reference.json. No differing trained binary is reported. The one-time cutover script is historical under docs/migration_tools; do not execute it from its relocated location.

Rollback without overwriting: stop services, preserve current V2 source/state, create a new empty sibling restore directory, then restore the snapshot contents according to manifest and verify each hash. Restore excluded dependencies separately. Alternatively reverse retirement mappings only into an empty intended destination after resolving/inspecting absolute targets. Never reset/clean Git or overwrite unknown work. Moving the archived environment breaks root `.pth` until replaced.

Git history was untouched. Existing modified/deleted/untracked work was not reset. New layout naturally shows many tracked deletions and new untracked folders until a human reviews a commit. No commit/push, training, Optuna resume or artifact rewrite occurred. Rebuildable caches can be discarded after checks; private state and unknown files stay preserved.

Final version-control snapshot: V2_GIT_STATE.json. On main, 4 modified, 2,792 deleted-path records and 137 untracked-file records at capture; deletion records include the pre-existing 2,623 and reversible retirement, not permanent loss. Cached Python bytecode and temporary extracted package checks are regenerable; authoritative source/artifact backups remain untouched.

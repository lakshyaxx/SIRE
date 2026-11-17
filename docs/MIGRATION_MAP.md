# V2 staging and cutover map

Verified current snapshot: `C:/Users/laksh/SIRE_SAFETY_BACKUPS/v2_20261117_000722`; 9,513 files, 3,081,859,612 bytes. Unchanged files link to verified immutable prior backup copies, never to active workspace files. New/changed files were copied. Every snapshot file was SHA-256 compared. Rebuildable environments, node_modules and caches were excluded; package freeze and binary Git patches preserved.

| Old active path | New active path | Role |
| --- | --- | --- |
| backend/ | app/api/ | Single FastAPI service |
| engine/ | app/core, app/prediction, app/providers, app/investigation | Separate domains |
| frontend/ | web/ | Chat-first presentation |
| model_store/ | ml/registry/ | Canonical catalog and current verification |
| Phase_A_RUL_Training/CMAPSS inference dependencies | ml/artifacts/cmapss/ | Exact native hierarchy retained for loading compatibility |
| samples/ | data/demo, data/knowledge | Provenance-backed sample sources |
| Phase A tests | tests/legacy_cmapss | Original logic; only fixture path discovery adapted |

`ml/registry/migration_map.json` records every original/current inference path, size and SHA-256. The hierarchy inside the immutable ML container is deliberately retained: the native loaders derive `artifacts/`, `models/` and `common/` from their own file locations. Flattening this would alter loading behavior. All application code uses the single consolidated catalog, not a Phase folder.

No old active directory is removed before new runtime parity and application checks pass. Retirement will be reversible relocation into a named external quarantine with a path manifest. No irreversible deletion set is currently authorized. Training records, reports, paused studies and old V1 source are preserved. Git history and existing working changes must not be reset or cleaned.

## Cutover completed

Old active folders were reversibly retired after inference/parity and application checks. RETIREMENT_MANIFEST.json has exact moves; CLEANUP_MANIFEST.md documents rollback and the root venv external third-party dependency. V2_PRESERVATION_EVIDENCE.json rechecks relocated files, including one explained regenerated audit JSON. No permanent deletion.

The machine map now covers all 813 indexed files, including recovered pre-tuning archive members and source data. Two explicitly labeled path-only predict.py adapters retain exact original source beside them; no binary conversion occurred.

# Preservation and rollback

User authorization on 2026-11-16 explicitly permits the repository-wide build and overrides the former active-phase and single-step restriction. No authorization for permanent deletion or public publishing has been given.

Verified external snapshot: `C:/Users/laksh/SIRE_SAFETY_BACKUPS/snapshot_20261116_223519`.

The private snapshot contains 9,373 files totaling 2,943,176,784 bytes. Every copied file was SHA-256 compared with its original. `manifest.json` SHA-256: `e8b3524c194cf5caa5141174acfdbad2236d6f0d65829909f2e32c060a13cbb3`.

Included: `.git` history/references/index, working files including untracked artifacts, research code, reports, datasets, both original ZIPs. Also saved `git_status.txt`, binary staged/unstaged patches and `environment_freeze.txt`. Excluded only `.venv`, `__pycache__`, `.pytest_cache`, `.ruff_cache`, `node_modules`. Existing environments were not deleted. Backups are private and have not been uploaded.

Initial Git state: branch `main`, HEAD `424432f`; 35 modified paths, 2,623 deleted paths, 3,878 untracked paths. These were pre-existing. Both original ZIPs passed Python `ZipFile.testzip()`.

No original model, preprocessor, calibration, study, source or report has been moved or rewritten. `model_store/manifest.json` points to original files and records byte hashes for inference dependencies, rather than duplicating binaries. `model_store/verification.json` records new CPU smoke outputs separately from historical evaluations.

The registry has a known metadata discrepancy: FD002 quantiles select seed 43 while their artifact directory text mentions seed 42. The new catalog records both the historical reference and the resolved seed path; the native loader chooses the actual files. Ensemble uncertainty also has historical seed-reference differences. The loader remains authoritative; no saved calibration is changed.

Rollback: stop the new app. Preserve any subsequent user edits first. Compare the snapshot manifest before restoring individual original paths from `workspace/`; never restore the entire tree blindly or run Git reset/clean. The new `backend/`, `engine/`, `frontend/`, `config/`, `model_store/`, `scripts/`, `tests/`, `docs/` are additive. The previous README and STATUS are in the snapshot. The Python package freeze allows rebuilding the earlier environment; `requirements-app.txt` additions modify the installed environment but not trained artifacts.

Deletion manifest: empty. Existing phase trees and ZIPs remain intact. External archival and removal of old research require a later reviewed manifest and explicit approval.

## V2 — 2026-11-17

Fresh snapshot v2_20261117_000722: 9,513 files / 3,081,859,612 bytes, every SHA checked. Verified runtime cutover followed; old trees are under v2_retired_20261117 with exact retirement manifest. No reset/clean, permanent deletion, training or binary rewrite. Current paths/rollback: CLEANUP_MANIFEST.md, MIGRATION_MAP.md and ml/registry/migration_map.json. Entries above are historical V1 audit trail, not current startup directions.

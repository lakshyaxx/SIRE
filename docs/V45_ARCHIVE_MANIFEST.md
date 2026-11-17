# V4.5 dependency-aware archive decision

No protected model/research file was moved or deleted. A primary-route policy does not establish that other artifacts are unused. In particular, the saved ensemble references multiple constituent families and fitted preprocessors. All168catalog routes remain publicly selectable inside the local app; removing their files would break existing behavior.

Machine-readable audit: `.runtime/v45/archive_dependency_audit.json`. It records168model entries with exact artifact directories, prediction modules, weight/preprocessing/calibration references and declared environment dependencies;813captured inference files have their original path, bytes, expected SHA, reason, retained-in-place disposition and null archive path. The actual hash validation reference is included. Empty moved/deleted lists reflect the executed no-move decision, not an inferred disk-saving metric.

## Primary saved pathways

| Dataset | Low latency | Advanced | Deep |
|---|---|---|---|
| FD001 |fd001-01_lightgbm-s42|fd001-08_ensemble-s42|fd001-03_bilstm_attention-s42|
| FD002 |fd002-01_lightgbm-original-s42|fd002-08_ensemble-s44|fd002-03_bilstm_attention-s42|
| FD003 |fd003-01_lightgbm-original-s42|fd003-08_ensemble-s42|fd003-03_bilstm_attention-s42|
| FD004 |fd004-01_lightgbm-original-s42|fd004-08_ensemble-s42|fd004-03_bilstm_attention-s42|

Selection is configuration-based over ready saved families/seeds, not tuning on a holdout set. Original catalog defaults and original catalog bytes are preserved; API annotations retain `catalog_default`. Other research routes are available on demand. All12selected routes ran with genuine existing compatible saved engine samples.

## Checkpoint and rollback inventory

Before edits: `pre_edit_source.zip` (271files,747277bytes), `pre_edit_production.sqlite3` (consistent1728512byte backup), `tracked_changes.patch` (620676407bytes), and verified `committed_baseline.bundle` (285652966bytes) under `.runtime/v45/backups/`. HEAD is `424432f96b2b9efabc41179e3b9271a9a881e24c`. `.git` was not changed; the inherited2792deleted-path records remain inherited. The later `v4_source.zip` snapshot includes early V45 additions and must not be represented as the pre-edit V4 checkpoint.

Before main cutover: additional `frontend_before_cutover.zip` and consistent `production_before_cutover.sqlite3`. New assets were copied without removing old assets. Rollback requires stopping only the owned web process, restoring source/frontend from the authoritative checkpoints, and restarting the local launcher. Do not restore an old DB over user activity; reconcile/backup any later state first. The current migration only adds V45 tables and leaves all13old table rows equal to the pre-edit backup.

The original V2/V3/V3.2 runtime ZIPs retain their original SHA values. Protected native813files and frozen stress7956files pass SHA/size verification before and after cutover; full results are in `.runtime/v45/preservation_after_cutover.json`. The external preserved environment remains required by the existing root `.venv`; no dependency cleanup or clean-environment portability is claimed. Archiving large disk files would not by itself improve inference latency; bounded lazy residency provides that runtime boundary without moving research.

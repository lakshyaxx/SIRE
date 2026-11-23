# 01_data_pipeline

Read AGENTS.md and PROJECT_MAP.md. Implement Phase 1 only, for C-MAPSS (start with FD001, make it work for FD002-FD004 via config):
loaders/base_loader.py, loaders/cmapss_loader.py, validators.py, rul_labels.py (clip at 125), preprocessing.py (drop constant sensors, scale on train only, optional per-operating-condition normalization for FD002/FD004), windowing.py, splits.py (engine-level), dataset.py, scripts/prepare_data.py, and tests/test_loaders.py + tests/test_windowing.py.
Inspect the real files in data/raw/cmapss first. Leave the N-CMAPSS loader and downsampling.py untouched. Do not touch other phases.

# NCMAPSS results

Written by code, never edited by hand:

- `data_audit.md` - Step 0 audit of the real files.
- `splits.json` - the train/validation unit ids used by every model.
- `comparison.csv` - one row per (track, dataset, model, seed, split, level, target_type). Columns are defined in Phase A README 6.1.
- `REPORT.md` - regenerated after every model, with window-level and flight-cycle-level tables, deltas vs the LightGBM baseline and vs the best so far, honest verdicts.
- `figures/` - audit and report figures.
- `artifacts/<DATASET>/` - scaler, cached downsampled series, split ids and feature configuration shared by the models.

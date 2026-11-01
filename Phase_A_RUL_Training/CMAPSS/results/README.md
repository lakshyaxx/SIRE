# CMAPSS results

Written by code, never edited by hand:

- `data_audit.md` - Step 0 audit of the real data.
- `splits.json` - the train/validation engine ids used by every model.
- `comparison.csv` - one row per (track, dataset, model, seed, split, level, target_type). Columns are defined in Phase A README 6.1.
- `REPORT.md` - regenerated after every model: ranking tables, deltas vs the LightGBM baseline and vs the best so far, figures, honest verdicts.
- `figures/` - audit and report figures.
- `artifacts/<DATASET>/` - preprocessor, split ids and feature configuration shared by the models.

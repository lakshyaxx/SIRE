# 02_lightgbm_baseline

Implement Phase 2: features/engineering.py, models/base.py, registry.py, lightgbm_model.py, training/train.py, evaluation/metrics.py (RMSE + NASA score), evaluate.py, explain.py (SHAP). Train LightGBM on the processed data, log results to docs/experiment_log.md and results/metrics/.

Reproduction commands: `python scripts/prepare_data.py --subset FD001`, then `python -m pdm.training.train --model lightgbm --subset FD001`. The configured run uses an engine-level validation split and reports metrics at each validation engine's terminal cycle. The official test score uses the provided per-engine RUL reference and terminal predictions after the fixed three-seed configuration is trained.

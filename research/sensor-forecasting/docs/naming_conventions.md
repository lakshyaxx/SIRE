# Naming conventions
- Packages and files: snake_case. Classes: PascalCase. Configs: <topic>/<name>.yaml.
- Models are referred to by registry name: lightgbm, bilstm_attention, cnn_transformer, lstm_autoencoder, ensemble.
- Artifacts: models_store/checkpoints/<dataset>_<subset>_<model>_seed<N>.<ext>
- Results: results/metrics/<dataset>_<subset>_<model>.json
- Phases are numbered 1..11 (see docs/codex_prompts/).

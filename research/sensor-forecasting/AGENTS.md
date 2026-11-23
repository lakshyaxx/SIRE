# Instructions for Codex / coding agents
Project: predictive-maintenance platform, RUL prediction + later agentic AI layer.
Active dataset: C-MAPSS (start with FD001, then FD002-FD004). N-CMAPSS is an optional later extension. Active dataset is set in configs/data/active.yaml.
Always read PROJECT_MAP.md first. Work only on the phase named in the prompt (see docs/codex_prompts/).

Rules
1. Skeleton files already exist. Fill them in; do not rename or move them without asking.
2. Everything is config-driven (configs/). No hard-coded paths: use src/pdm/common/paths.py.
3. Split train/val by engine unit, never by row. Fit scalers on train only.
4. Report RMSE and the NASA asymmetric score. Use 3 seeds for final numbers.
5. The LLM layers never produce numeric predictions. Only models via inference/predictor.py do.
6. Do not touch frontend/. It is a Figma export that will be added later.
7. Add or update a test for everything you implement. Run pytest before finishing.
8. Log every experiment to docs/experiment_log.md.
9. Keep the code readable and short, with type hints and docstrings.
Environment: Python 3.10+, install with pip install -r requirements.txt; package in src/ (pip install -e .).

# PROJECT MAP
Two-line purpose of every top-level folder.
Active dataset: C-MAPSS (FD001 first). N-CMAPSS is an optional later extension (configs/data/active.yaml switches).

| Path | Purpose |
|---|---|
| configs/ | All settings in YAML (data, models, training, pipeline, agent, rag, hypothesis, multimodal). Change behavior here, not in code. |
| data/ | raw/cmapss holds the downloaded C-MAPSS files (raw/ncmapss reserved for later), interim/processed are generated, knowledge_base/ feeds RAG, uploads/ holds engineer files. |
| src/pdm/common | Shared config, paths, logging, seeds and the data contracts (schemas) every module uses. |
| src/pdm/data | Loading, validating, labeling (RUL), scaling, windowing and splitting the datasets. |
| src/pdm/features | Hand-made features for tabular models and health indicators. |
| src/pdm/forecasting | Sensor experiment paths, fixed-origin benchmark CLI, leakage-safe input preparation and benchmark reports. |
| src/pdm/models | RUL model modules plus statsmodels sensor forecasting adapters and optional PyTorch Forecasting TFT. |
| src/pdm/training | Training loops, losses, callbacks, tuning and the train CLI. |
| src/pdm/evaluation | RUL metrics (including NASA score), aligned sensor forecast metrics, SHAP explanations, ablations and report tables. |
| src/pdm/inference | The core predict(df) function and saved-model loading. Everything above calls this. |
| src/pdm/ingestion | Detects and prepares csv, docx, image and audio uploads. |
| src/pdm/multimodal | LLM client, vision, speech-to-text, text-to-speech. |
| src/pdm/rag | Chunking, embeddings, indexing and retrieval of evidence from the knowledge base. |
| src/pdm/agent | LLM orchestrator, its tools, planner and memory. |
| src/pdm/hypothesis | Generate, backtest, cross-test and rank hypotheses. |
| src/pdm/reporting | Builds the final engineer report. |
| src/pdm/pipeline | Stages and the orchestrator that runs the full data flow. |
| src/pdm/api | FastAPI backend that the Figma frontend will connect to. |
| frontend/ | Placeholder only. Figma export and API contract go here later. |
| models_store/ | Trained checkpoints, scalers and exported models. |
| results/ | Archived metrics and figures, RUL outputs, tables and logs. New classical experiment outputs go in individual directories under runs/. |
| scripts/ | RUL pipeline runners and classical experiment entry points grouped under training/, analysis/, evaluation/ and visualization/. |
| diffmodels/ | Forecasting model launchers and companion analysis, comparison and plotting commands. |
| tests/ | Unit and end-to-end tests. |
| docs/ | Architecture, naming conventions, experiment log, and the Codex prompts per phase. |

## Data flow
upload -> ingestion/router -> inference/predictor (RUL, uncertainty, health index, top sensors)
-> rag/retriever -> agent -> hypothesis (generate, backtest, rank) -> reporting -> api -> frontend

## Phases
1 data | 2 LightGBM baseline | 3 deep models | 4 autoencoder | 5 ensemble + eval | 6 predictor + API
7 ingestion + pipeline | 8 agent | 9 RAG + hypothesis + report | 10 multimodal + voice | 11 frontend integration
Thursday target: phases 1 to 5 on one dataset subset.

# Architecture
Engineer upload (csv / docx / image / voice)
  -> ingestion/router
  -> inference/predictor  (deterministic models: RUL, uncertainty, health index, top sensors)
  -> rag/retriever        (manuals, past failures, logs)
  -> agent/agent          (LLM orchestrator, calls tools)
  -> hypothesis/*         (generate, backtest, cross-test, rank)
  -> reporting/report_builder -> api -> frontend (Figma)

Rules: the LLM never produces numeric predictions; models do. Every layer calls predictor.predict(df).

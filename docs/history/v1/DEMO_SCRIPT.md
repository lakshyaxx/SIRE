# Honest local demo

1. Start the built app using `scripts/dev.ps1` on Windows, or the documented Python launcher elsewhere.
2. Open the loopback URL, select FD001 and an actual source engine, then Analyze engine. Show measured RUL, cycles, model ID, artifact version and padding warnings.
3. Open Assets. Change engine and sensor; the chart loads that engine's real raw readings.
4. Open Models. Inspect all preserved families and their actual compatibility status. Choose two RUL routes to compare on the same engine. Anomaly output uses a separate tool.
5. Ask a question in Investigation. Show measured model evidence and quoted project guidance. If Ollama is missing, explicitly show `llm_unavailable` and no generated hypotheses.
6. Open Vision. With no local model, show the honest unavailable state. Only demonstrate real image observations after an approved installed model has passed a real image call.
7. State limitations: simulated aircraft data, operating-cycle forecasts, no diagnosis from a photo or model attribution, no live customer sensors, no certified maintenance decisions.

Use Settings to show actual readiness. Offline fallback is the real local ML path and local document retrieval; no canned replacement predictions. Existing research CSV/PDF results are historical evidence, not freshly rerun evaluation.

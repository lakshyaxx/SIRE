# V3 scenario evaluation

{
  "N": 20,
  "seeds": [
    42,
    43
  ],
  "engine": "deterministic_sire_facility_rules_1",
  "provider": "none; no LLM efficacy measured",
  "top1": {
    "correct": 12,
    "N": 16
  },
  "top3": {
    "correct": 16,
    "N": 16
  },
  "citation_validity": {
    "valid": 588,
    "total": 588
  },
  "normal_false_warnings": {
    "count": 0,
    "N": 2
  },
  "ambiguous_abstention": {
    "correct": 2,
    "N": 2
  },
  "mean_latency_seconds": 0.5406500000004598,
  "p95_latency_seconds": 0.625799999999981,
  "timeouts": 0,
  "limitations": [
    "Small engineered synthetic benchmark, not independent physical validation or LLM accuracy.",
    "Case rule catalogue and generator were designed together; results are an integration benchmark.",
    "Lead time is on a coarse synthetic hourly grid, evaluated at six prefixes.",
    "No natural-language unsupported-claim rate was measured."
  ]
}

Per-case actual measurements are in .runtime/v3_evaluation/results.json. No ground-truth label is read by investigator/API/knowledge modules.

| Seed | Scenario | Top-1 | Top-3 | Abstained | Lead hours | Tool calls |
| --- | --- | --- | --- | --- | --- | --- |
| 42 | 2148e52f-cc11-53f9-a202-5097e3a72dd7 | True | True | False | 24 | 7 |
| 42 | 3b10413c-be96-53a4-80ed-6d9cf8c2116f | False | True | False | 36 | 7 |
| 42 | 4b6c7714-32a6-5105-9d56-370a89321c3b | True | True | True | None | 7 |
| 42 | 5230d716-3ee7-5f40-92ff-178f46c5619d | True | True | False | 36 | 7 |
| 42 | 5b348df9-42e2-5b15-bc4e-41c673ea36e9 | False | False | True | None | 7 |
| 42 | 6ad01ae4-6940-5687-bf2f-06d010ace97c | False | False | True | None | 7 |
| 42 | 88367e1b-7d7c-54bb-b323-152cb204cb22 | True | True | False | 24 | 7 |
| 42 | 9d084b67-e03b-5daa-b2ec-357f0439ddb0 | True | True | False | 36 | 7 |
| 42 | cfc6194f-edaf-50cf-9b68-01ac62a04757 | True | True | False | 24 | 7 |
| 42 | e33bec6c-29a6-59f1-afc0-a490f53488eb | False | True | True | None | 7 |
| 43 | 0c6b1a0c-b5c2-5504-81a0-9be67dc953b5 | True | True | False | 24 | 7 |
| 43 | 2fd06fe8-29b3-5e8a-adb6-fcc8dc6a0913 | False | False | True | None | 7 |
| 43 | 35b79c62-5138-587a-af59-dbaf1e24fcc6 | True | True | False | 24 | 7 |
| 43 | 5cfd7cee-b286-51f8-bde7-0d177ae800ff | False | True | True | None | 7 |
| 43 | 7b5fd686-f616-551d-8952-095b68fb57ba | False | False | True | None | 7 |
| 43 | cf4e762a-858a-5c7b-9afd-b01c2760f1d9 | True | True | True | None | 7 |
| 43 | eb357f85-7065-57d7-b2af-7fd9cc8f3866 | False | True | False | 36 | 7 |
| 43 | ebc6c510-0c94-5c5b-b7f3-e524686900a2 | True | True | False | 36 | 7 |
| 43 | f5b838b2-59fd-5f52-8729-541aa4c731d0 | True | True | False | 24 | 7 |
| 43 | f76e8f3f-b638-5483-a274-8254251655c1 | True | True | False | 36 | 7 |
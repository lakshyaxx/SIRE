# SIRE C-MAPSS demonstration model card

Provenance: project-authored integration notes derived from the existing SIRE README and Phase A inference contracts. This is software documentation, not an equipment maintenance manual.

C-MAPSS demonstration assets are simulated turbofan sensor histories. Remaining useful life (RUL) estimates use operating cycles. A cycle-to-calendar conversion is not available. These estimates are not certified maintenance limits and cannot establish a physical root cause.

The saved predictors require dataset-matched C-MAPSS histories with engine unit, cycle, three operating settings and twenty-one sensors. Fitted preprocessing is loaded from the original training artifacts. Generic vibration or vehicle CSV files are not compatible merely because they contain numeric readings.

The autoencoder anomaly detector is experimental. An anomaly score is not remaining useful life. A model's feature contributions describe its prediction, not proof of a failed component.

Photographs can support visible observations. They cannot prove internal damage or supply a sensor-based RUL estimate. A real component photograph and a NASA simulated engine are unrelated evidence sources unless an independently validated relationship exists.

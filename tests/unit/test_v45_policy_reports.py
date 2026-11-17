"""Production selection is reversible; concise export retains every immutable row in JSON."""

import hashlib
import json
from app.prediction import hub
from app.prediction.policy import models, selections
from app.core.config import MANIFEST
from app.reports.evidence_case import source_summary


def test_three_primary_pathways_preserve_full_original_catalog_and_defaults():
    before = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    original = hub.catalog()
    rows = models()
    selected = selections(original)
    assert len(rows) == len(original)
    assert {row["model_id"] for row in rows} == {row["model_id"] for row in original}
    assert len([row for row in rows if row["default"]]) == 4
    assert all(row["family"] == "01_lightgbm" for row in rows if row["default"])
    assert all(
        set(values) == {"low_latency", "advanced", "deep"}
        for values in selected.values()
    )
    assert selected["FD002"]["advanced"] == next(
        row["model_id"]
        for row in original
        if row["dataset"] == "FD002" and row["default"]
    )
    assert all(
        row["catalog_default"]
        == next(
            old["default"] for old in original if old["model_id"] == row["model_id"]
        )
        for row in rows
    )
    assert hashlib.sha256(MANIFEST.read_bytes()).hexdigest() == before


def test_source_preview_never_mutates_full_rows_and_marks_truncation():
    record = {
        "observation": {
            "rows": [{"test_only_original_id": n} for n in range(5001)],
            "excerpt": "test-only " * 200,
        }
    }
    frozen = json.dumps(record, sort_keys=True)
    summary = source_summary(record)
    assert summary["source_rows"]["count"] == 5001
    assert summary["source_rows"]["last"] == [{"test_only_original_id": 5000}]
    assert (
        summary["excerpt"]["truncated"] is True
        and len(summary["excerpt"]["excerpt"]) == 1200
    )
    assert json.dumps(record, sort_keys=True) == frozen

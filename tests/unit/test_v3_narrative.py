"""Explicit test-only numbers verify that unsupported model language cannot become a completed answer."""

import pytest
from app.core.errors import SireError
from app.prediction.narrative import facts, validate

RESULT = {
    "rul_cycles": 10.22,
    "last_cycle": 8,
    "interval": [4.12, 16.32],
    "model_id": "test-only-model",
    "dataset": "test-only",
    "asset_id": "test-only",
    "interval_method": "test-only interval",
}


@pytest.mark.parametrize(
    "text",
    [
        "10.2 cycles with 95% confidence",
        "95 percent confidence",
        "confidence interval is narrow",
        "99 cycles remaining",
        "Measured RUL is 10.2 cycles",
        "Remaining life is 3 days",
    ],
)
def test_unsupported_narrative_is_rejected(text):
    with pytest.raises(SireError):
        validate(text, RESULT)


def test_rounding_and_native_facts_are_valid():
    validate(
        "The estimate is 10.2 cycles; endpoints 4.1 cycles and 16.3 cycles are native estimates.",
        RESULT,
    )
    assert "10.22" in facts(RESULT) and "inference" in facts(RESULT)


def test_anomaly_is_never_rendered_as_none_cycles_or_estimated_life():
    anomaly = {
        **RESULT,
        "rul_cycles": None,
        "interval": None,
        "anomaly": {"anomaly_score": 0.7, "threshold": 0.5},
    }
    assert "None operating cycles" not in facts(anomaly)
    validate("This is an experimental anomaly indicator, not a life estimate.", anomaly)
    with pytest.raises(SireError):
        validate("RUL is 8 cycles.", anomaly)

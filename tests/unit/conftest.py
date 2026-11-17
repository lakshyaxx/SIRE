"""Actual source histories for preserved logic regression tests."""

import pytest
from app.prediction.telemetry import asset_history


@pytest.fixture
def history():
    """Use the real source engine rather than synthetic measurements."""
    return asset_history("FD001-ENGINE-001", "FD001")

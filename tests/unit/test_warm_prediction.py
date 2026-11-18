"""Resident adapter lifecycle controls, separate from native parity benchmarking."""

import pytest

from app.core.errors import SireError
from app.prediction import worker


def test_resident_prediction_reuses_loader_and_rechecks_each_request(monkeypatch):
    loaded = []
    verified = []
    handlers = []

    def load(model_id):
        loaded.append(model_id)
        return model_id

    def check():
        if len(verified) == 2:
            raise SireError("artifact_integrity", "Test-only modified artifact", 503)
        verified.append(True)

    monkeypatch.setenv("MPLCONFIGDIR", "test-only")
    monkeypatch.setattr(worker, "catalog_fingerprint", lambda: "test-catalog")
    monkeypatch.setattr(worker, "_load_predictor", load)
    monkeypatch.setattr(worker, "verify_integrity", check)
    monkeypatch.setattr(worker, "serve", handlers.append)
    monkeypatch.setattr(
        worker,
        "_predict",
        lambda predictor, history: {"cycle": int(history.cycle.iloc[0])},
    )
    worker._serve_resident()
    handle = handlers[0]
    payload = {"model_id": "test-model", "catalog_fingerprint": "test-catalog"}
    for cycle in (1, 2):
        assert handle({**payload, "history": [{"cycle": cycle}]}) == {
            "output": {"cycle": cycle}
        }
    assert loaded == ["test-model"]
    with pytest.raises(SireError, match="modified artifact"):
        handle({**payload, "history": [{"cycle": 3}]})
    with pytest.raises(ValueError, match="registry changed"):
        handle({**payload, "catalog_fingerprint": "changed"})

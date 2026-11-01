"""Registry serialization tests."""

from common.registry import read_registry, write_registry


def test_registry_round_trip(tmp_path) -> None:
    """Persist and reload a JSON-compatible registry without cwd assumptions."""
    path = tmp_path / "model_registry.json"
    registry = {"datasets": {"FD001": {"best_by_val_rmse": "01_lightgbm"}}}
    assert write_registry(registry, path) == path
    assert read_registry(path) == registry

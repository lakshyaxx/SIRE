"""Engine-level split reproducibility and persistence tests."""

from common.splits import get_or_create_split, split_engine_ids


def test_split_is_deterministic_and_engine_disjoint(tmp_path) -> None:
    """Persist a seeded split without any engine crossing the partition boundary."""
    ids = list(range(1, 101))
    train, val = split_engine_ids(ids, val_fraction=0.2, seed=42)
    train_again, val_again = split_engine_ids(ids, val_fraction=0.2, seed=42)
    assert train == train_again
    assert val == val_again
    assert set(train).isdisjoint(val)
    assert sorted(train + val) == ids
    split = get_or_create_split("FD001", ids, path=tmp_path / "splits.json")
    loaded = get_or_create_split("FD001", ids, path=tmp_path / "splits.json")
    assert split == loaded


def test_saved_split_rejects_changed_engine_inventory(tmp_path) -> None:
    """Do not silently reuse a split after the dataset engine inventory changes."""
    path = tmp_path / "splits.json"
    get_or_create_split("FD004", list(range(1, 250)), path=path)
    try:
        get_or_create_split("FD004", list(range(1, 249)), path=path)
    except ValueError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("changed engine inventory should be rejected")

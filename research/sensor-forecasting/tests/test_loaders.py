"""Tests for C-MAPSS loading, labels, validation and engine splits."""
import pandas as pd
import pytest

from pdm.data.loaders.cmapss_loader import CMapssLoader, COLUMNS
from pdm.data.rul_labels import add_rul_labels
from pdm.data.splits import split_units
from pdm.data.validators import validate_cmapss


def test_loader_reads_fd001_and_test_rul():
    loader = CMapssLoader("data/raw/cmapss")
    train = loader.load_train("FD001")
    test, rul = loader.load_test("FD001")
    assert list(train.columns) == COLUMNS
    assert train.unit.nunique() == 100
    assert test.unit.nunique() == len(rul) == 100
    validate_cmapss(train)
    validate_cmapss(test, require_complete=False)


def test_rul_is_clipped_and_decreases_by_cycle():
    frame = pd.DataFrame({"unit": [1, 1, 1], "cycle": [1, 2, 3]})
    assert add_rul_labels(frame, clip=2).rul.tolist() == [2, 1, 0]


def test_split_keeps_units_disjoint():
    units = list(range(10))
    train, val = split_units(units, random_state=7)
    assert set(units[i] for i in train).isdisjoint(units[i] for i in val)


def test_validator_rejects_duplicate_cycle():
    row = [1, 1, *([0.0] * 24)]
    frame = pd.DataFrame([row, row], columns=COLUMNS)
    with pytest.raises(ValueError, match="Duplicate"):
        validate_cmapss(frame)

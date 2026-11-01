"""Parsing and basic schema validation tests."""

from pathlib import Path

import pandas as pd
import pytest

from common.config import RAW_COLUMNS, cmapss_root
from common.data import load_cmapss_dataset, load_train


def test_parse_actual_fd001_columns_and_row_counts() -> None:
    """Parse the supplied FD001 files, including their trailing whitespace."""
    data = load_cmapss_dataset("FD001")
    assert list(data.train.columns[:26]) == list(RAW_COLUMNS)
    assert data.train.shape[0] == 20631
    assert data.test.shape == (13096, 26)
    assert data.test_truth.shape == (100, 3)
    assert data.train["rul_raw"].min() == 0
    assert data.train["rul_clipped"].max() == 125


def test_load_train_accepts_trailing_whitespace(tmp_path: Path) -> None:
    """Ignore an empty trailing field after whitespace-delimited data."""
    values = [1, 1, 0.1, 0.2, 0.3, *[float(index) for index in range(21)]]
    file_path = tmp_path / "train_small.txt"
    file_path.write_text(" ".join(map(str, values)) + "   \n" + " ".join(map(str, [1, 2, 0.1, 0.2, 0.3, *[float(index) for index in range(21)]])) + " \n", encoding="utf-8")
    frame = load_train(file_path)
    assert frame.shape == (2, 28)
    assert frame.loc[0, "rul_raw"] == 1
    assert frame.loc[0, "rul_clipped"] == 1


def test_all_subset_files_and_official_rul_counts_match_test_engines() -> None:
    """Check data row alignment, including the observed FD004 249/248 split."""
    root = cmapss_root() / "data"
    expected = {"FD001": (100, 100), "FD002": (260, 259), "FD003": (100, 100), "FD004": (249, 248)}
    for dataset, (train_count, test_count) in expected.items():
        loaded = load_cmapss_dataset(dataset)
        assert loaded.train["unit"].nunique() == train_count
        assert loaded.test["unit"].nunique() == test_count
        assert len(loaded.test_truth) == test_count
        assert (root / f"train_{dataset}.txt").is_file()
        assert (root / f"test_{dataset}.txt").is_file()
        assert (root / f"RUL_{dataset}.txt").is_file()


def test_wrong_column_count_is_rejected(tmp_path: Path) -> None:
    """Reject files that do not have the 26-column CMAPSS layout."""
    path = tmp_path / "train_bad.txt"
    pd.DataFrame([[1, 1, 2]]).to_csv(path, sep=" ", header=False, index=False)
    with pytest.raises(ValueError, match="expected 26 columns"):
        load_train(path)

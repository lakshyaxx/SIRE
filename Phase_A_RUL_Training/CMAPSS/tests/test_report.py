"""Report row replacement tests."""

import pandas as pd

from common.report import COMPARISON_COLUMNS, generate_report, replace_comparison_rows


def _row(rmse: float) -> dict[str, object]:
    """Build one complete result record for report persistence tests."""
    return {
        "track": "CMAPSS",
        "dataset": "FD001",
        "model": "01_lightgbm",
        "seed": 42,
        "split": "test",
        "level": "engine",
        "target_type": "raw",
        "n": 100,
        "rmse": rmse,
        "mae": rmse - 1,
        "mse": rmse**2,
        "r2": 0.5,
        "nasa_score": 20.0,
        "nasa_score_mean": 0.2,
        "n_params": 10,
        "train_seconds": 1.5,
        "device": "cpu",
        "config_hash": "abc",
        "timestamp": "2026-11-01T00:00:00+00:00",
    }


def test_comparison_rows_are_replaced_not_duplicated(tmp_path) -> None:
    """A rerun with the same identity key replaces the old metrics."""
    csv_path = tmp_path / "comparison.csv"
    replace_comparison_rows([_row(10.0)], csv_path)
    result = replace_comparison_rows([_row(8.0)], csv_path)
    stored = pd.read_csv(csv_path)
    assert list(stored.columns) == list(COMPARISON_COLUMNS)
    assert len(result) == len(stored) == 1
    assert stored.loc[0, "rmse"] == 8.0


def test_report_is_generated_from_rows(tmp_path) -> None:
    """Generate Markdown for an existing row and an empty comparison file."""
    csv_path = tmp_path / "comparison.csv"
    report_path = tmp_path / "REPORT.md"
    replace_comparison_rows([_row(10.0)], csv_path)
    generate_report(csv_path, report_path, tmp_path / "figures")
    assert "01_lightgbm" in report_path.read_text(encoding="utf-8")
    empty_csv = tmp_path / "empty_comparison.csv"
    pd.DataFrame(columns=COMPARISON_COLUMNS).to_csv(empty_csv, index=False)
    generate_report(empty_csv, report_path, tmp_path / "figures")
    assert "No model results" in report_path.read_text(encoding="utf-8")

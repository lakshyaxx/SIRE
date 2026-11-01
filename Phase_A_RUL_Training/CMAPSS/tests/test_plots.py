"""Diagnostics plot creation test."""

import numpy as np
import pandas as pd

from common.plots import plot_loss_curve, plot_metric_history, plot_prediction_diagnostics


def test_plot_helpers_write_expected_figures(tmp_path) -> None:
    """Create history and prediction plots for a tiny real sample."""
    history_path = plot_loss_curve(
        pd.DataFrame({"epoch": [1, 2], "train_loss": [1.0, 0.5], "val_rmse": [3.0, 2.0]}),
        tmp_path / "loss.png",
    )
    metric_path = plot_metric_history(
        pd.DataFrame({"iteration": [1, 2], "train_rmse": [4.0, 3.0], "val_rmse": [5.0, 4.0]}),
        "iteration",
        "train_rmse",
        "val_rmse",
        tmp_path / "metric.png",
        "RMSE",
    )
    figures = plot_prediction_diagnostics(np.array([10, 20, 40]), np.array([11, 17, 48]), tmp_path / "diagnostics")
    assert history_path.is_file()
    assert metric_path.is_file()
    assert len(figures) == 4
    assert all(path.is_file() for path in figures)

"""Regression coverage for reorganized sensor experiment paths."""
import runpy
from importlib import import_module
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest
import yaml

from pdm.common.paths import ROOT
from pdm.forecasting import sensor_experiment


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    """Configure a small repository with no dependency on the downloaded dataset."""
    configs = tmp_path / "configs"
    (configs / "forecasting").mkdir(parents=True)
    (configs / "data").mkdir()
    (configs / "forecasting" / "sensor_experiment.yaml").write_text(
        yaml.safe_dump({"subset": "FD001", "unit": 1, "sensor": 2, "runs_dir": "results/runs"}),
        encoding="utf-8",
    )
    (configs / "data" / "cmapss.yaml").write_text("raw_dir: raw\n", encoding="utf-8")
    monkeypatch.setattr(sensor_experiment, "CONFIG_DIR", configs)
    monkeypatch.setattr("pdm.common.paths.ROOT", tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    return tmp_path


def test_sensor_selection_matches_original(experiment):
    raw_dir = experiment / "raw"
    raw_dir.mkdir()
    rows = [[unit, cycle, 0, 0, 0, 99, reading, *([0] * 19)]
            for unit, cycle, reading in [(1, 2, 3.25), (2, 1, 12.5), (1, 1, 1.25)]]
    path = raw_dir / "train_FD001.txt"
    path.write_text("\n".join(" ".join(map(str, row)) for row in rows), encoding="utf-8")
    frame = pd.read_csv(path, sep=r"\s+", header=None)
    original = frame[frame[0] == 1].sort_values(1)[6].astype(float).reset_index(drop=True)
    pd.testing.assert_series_equal(sensor_experiment.load_sensor_series(), original)


def test_run_directories_preserve_existing_results(experiment):
    first = sensor_experiment.new_run_directory()
    report = first / "metrics" / "model_comparison_results.csv"
    report.write_text("saved result", encoding="utf-8")
    second = sensor_experiment.new_run_directory()
    assert first != second
    assert first.parent == second.parent == experiment / "results" / "runs"
    assert report.read_text(encoding="utf-8") == "saved result"
    assert (second / "figures" / "forecasts").is_dir()


@pytest.mark.parametrize(
    "script",
    sorted(path for folder in ("training", "evaluation", "analysis", "visualization")
           for path in (ROOT / "scripts" / folder).glob("*.py")),
    ids=lambda path: path.stem,
)
def test_diffmodels_launcher_dispatches_to_grouped_script(script: Path, monkeypatch):
    module = import_module(f"scripts.{script.parent.name}.{script.stem}")
    main = Mock()
    monkeypatch.setattr(module, "main", main)
    runpy.run_module(f"diffmodels.{script.stem}", run_name="__main__")
    main.assert_called_once_with()

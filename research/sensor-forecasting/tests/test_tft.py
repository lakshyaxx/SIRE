"""Optional TFT CPU training, inference and checkpoint checks."""
import json

import numpy as np
import pandas as pd
import pytest

from pdm.data.loaders.cmapss_loader import SENSOR_COLUMNS, SETTING_COLUMNS
from pdm.forecasting.benchmark_data import read_settings, split_history
from pdm.models.tft import TFTFit, decoder_input, fit_tft


def test_decoder_input_contains_only_observed_measurements():
    history = pd.DataFrame({"unit": [1, 1, 1], "sensor_2": [3., 4., 5.]},
                           index=pd.Index([1, 2, 3], name="cycle"))
    sample = decoder_input(history, pd.Index([4, 5]), 2)
    assert sample["cycle"].tolist() == [2, 3, 4, 5]
    assert sample["sensor_2"].tolist() == [4., 5., 5., 5.]
    with pytest.raises(ValueError, match="immediately following"):
        decoder_input(history, pd.Index([5, 6]), 2)


def test_tft_cpu_training_and_checkpoint(tmp_path):
    pytest.importorskip("pytorch_forecasting")
    rng = np.random.default_rng(7)
    frame = pd.DataFrame(rng.normal(size=(6 * 26, 24)), columns=[*SETTING_COLUMNS, *SENSOR_COLUMNS])
    frame["unit"] = np.repeat(np.arange(1, 7), 26)
    frame["cycle"] = np.tile(np.arange(1, 27), 6)
    targets = ["sensor_2", "sensor_3"]
    history, actual = split_history(frame, 1, targets, 3)
    config = read_settings("models", "tft_smoke.yaml") | {"limit_train_batches": 1, "limit_val_batches": 1}
    directory = tmp_path / "tft"
    model = fit_tft(frame, 1, targets, 3, config, 42, directory)
    prediction = model.predict(history, actual.index)
    assert prediction.shape == actual.shape
    assert prediction.index.equals(actual.index)
    assert np.isfinite(prediction.to_numpy()).all()
    pd.testing.assert_frame_equal(TFTFit.load(directory).predict(history, actual.index), prediction)
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    assert not set(metadata["train_units"]) & set(metadata["validation_units"])
    assert 1 not in metadata["train_units"] + metadata["validation_units"]
    assert (directory / "last.ckpt").is_file()
    assert "val_loss" in json.loads((directory / "history.jsonl").read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="matching run"):
        fit_tft(frame, 1, targets, 3, config, 43, tmp_path / "bad", directory / "last.ckpt")
    resumed = tmp_path / "resumed"
    restored = fit_tft(frame, 1, targets, 3, config | {"max_epochs": 2}, 42, resumed,
                       directory / "last.ckpt")
    assert restored.predict(history, actual.index).shape == actual.shape
    assert json.loads((resumed / "history.jsonl").read_text(encoding="utf-8"))["epoch"] == 1

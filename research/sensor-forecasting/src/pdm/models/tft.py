"""PyTorch Forecasting TFT for engine-disjoint sensor benchmarks."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from pdm.data.loaders.cmapss_loader import SENSOR_COLUMNS, SETTING_COLUMNS
from pdm.data.splits import split_units


def _dependencies() -> tuple:
    try:
        import torch
        import lightning.pytorch as pl
        from pytorch_forecasting import TimeSeriesDataSet, TemporalFusionTransformer
    except ImportError as error:
        raise ImportError("TFT requires the optional dependencies: pip install -e '.[tft]'") from error
    return torch, pl, TimeSeriesDataSet, TemporalFusionTransformer


def _features(frame: pd.DataFrame, static: list[str]) -> pd.DataFrame:
    data = frame.sort_values(["unit", "cycle"]).copy().reset_index(drop=True)
    for name in static:
        column = name.removeprefix("initial_")
        data[name] = data.groupby("unit")[column].transform("first")
    data["unit"] = data["unit"].astype(str)
    return data


def decoder_input(history: pd.DataFrame, index: pd.Index, encoder_length: int) -> pd.DataFrame:
    """Construct one inference window using only observed rows and future cycle IDs."""
    if (len(history) < encoder_length or not len(index)
            or list(index) != list(range(int(history.index[-1]) + 1,
                                         int(history.index[-1]) + 1 + len(index)))):
        raise ValueError("TFT needs a full encoder and immediately following forecast cycles")
    observed = history.tail(encoder_length).reset_index()
    future = pd.concat([observed.tail(1)] * len(index), ignore_index=True)
    future["cycle"] = index.to_numpy()
    return pd.concat([observed, future], ignore_index=True)


@dataclass
class TFTFit:
    """A fitted TFT, its training-only dataset parameters, and feature schema."""

    model: object
    parameters: dict
    targets: list[str]
    static: list[str]
    accelerator: str

    def predict(self, history: pd.DataFrame, index: pd.Index) -> pd.DataFrame:
        """Emit point forecasts on the original sensor scales."""
        _, _, dataset, _ = _dependencies()
        if len(index) != self.parameters["max_prediction_length"]:
            raise ValueError("TFT prediction horizon must match the fitted decoder length")
        data = _features(decoder_input(history, index, self.parameters["max_encoder_length"]), [])
        for name in self.static:
            data[name] = float(history[name.removeprefix("initial_")].iloc[0])
        samples = dataset.from_parameters(self.parameters, data, predict=True)
        outputs = self.model.predict(samples.to_dataloader(train=False, batch_size=1),
                                     mode="prediction", trainer_kwargs={"accelerator": self.accelerator,
                                                                        "devices": 1, "logger": False,
                                                                        "enable_progress_bar": False})
        tensors = outputs if isinstance(outputs, (list, tuple)) else [outputs]
        values = np.column_stack([tensor.detach().cpu().numpy().reshape(-1) for tensor in tensors])
        if values.shape != (len(index), len(self.targets)) or not np.isfinite(values).all():
            raise RuntimeError("TFT produced invalid forecast values")
        return pd.DataFrame(values, index=index, columns=self.targets)

    @classmethod
    def load(cls, directory: Path, accelerator: str = "cpu") -> "TFTFit":
        """Restore a trusted checkpoint and its associated preprocessing state."""
        torch, _, _, model_class = _dependencies()
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        parameters = torch.load(directory / "preprocessing.pt", map_location="cpu", weights_only=False)
        model = model_class.load_from_checkpoint(directory / "best.ckpt", map_location="cpu",
                                                 weights_only=False)
        return cls(model, parameters, metadata["targets"], metadata["static"], accelerator)


def fit_tft(frame: pd.DataFrame, benchmark_unit: int, targets: list[str], horizon: int,
            config: dict, seed: int, directory: Path, resume: Path | None = None) -> TFTFit:
    """Train with disjoint engine splits and save the best and resumable checkpoints."""
    torch, pl, dataset, model_class = _dependencies()
    from lightning.pytorch.callbacks import Callback, EarlyStopping, ModelCheckpoint
    from pytorch_forecasting.data import MultiNormalizer, NaNLabelEncoder, TorchNormalizer
    from pytorch_forecasting.metrics import MultiLoss, QuantileLoss

    static = list(config.get("static", []))
    observed = list(config.get("observed", []))
    if (not set(observed) <= set(SENSOR_COLUMNS)
            or not set(static) <= {f"initial_{name}" for name in SETTING_COLUMNS}
            or config.get("known") != ["cycle"]):
        raise ValueError("TFT supports sensor history, initial operating settings, and known cycle")
    encoder = config["encoder_length"]
    if (any(type(config[key]) is not int or config[key] < 1 for key in
            ("encoder_length", "hidden_size", "attention_head_size", "batch_size", "max_epochs", "threads"))
            or not 0 <= config["dropout"] < 1 or not config["learning_rate"] > 0
            or config["accelerator"] not in {"auto", "cpu", "gpu", "cuda"}):
        raise ValueError("Invalid TFT window, architecture, optimizer or accelerator setting")
    counts = frame.groupby("unit")["cycle"].size()
    eligible = counts[(counts >= encoder + horizon) & (counts.index != benchmark_unit)].index
    units = eligible[:config.get("unit_limit", len(eligible))].to_numpy()
    if len(units) < 2 or encoder < 2 or horizon < 2:
        raise ValueError("TFT requires two eligible training/validation engines and full windows")
    train_indices, val_indices = split_units(units, config["val_fraction"], config["split_seed"])
    train_units, val_units = units[train_indices], units[val_indices]
    used = frame.loc[frame["unit"].isin(units), ["unit", "cycle", *SETTING_COLUMNS, *SENSOR_COLUMNS]]
    signature = hashlib.sha256(pd.util.hash_pandas_object(used, index=False).values.tobytes()).hexdigest()
    metadata = {"targets": targets, "static": static, "benchmark_unit": benchmark_unit,
                "horizon": horizon, "seed": seed, "data_hash": signature,
                "train_units": train_units.tolist(), "validation_units": val_units.tolist(),
                "config": {key: value for key, value in config.items() if key != "max_epochs"}}
    if resume is not None:
        previous = json.loads((resume.parent / "metadata.json").read_text(encoding="utf-8"))
        if metadata != previous or resume.name != "last.ckpt":
            raise ValueError("Resume requires a matching run's last.ckpt and metadata")

    class History(Callback):
        """Record epoch losses without requiring an optional logging backend."""

        def on_validation_end(self, trainer, model):
            if not trainer.sanity_checking:
                losses = {key: float(value.detach().cpu()) for key, value in trainer.callback_metrics.items()
                          if key in {"train_loss", "train_loss_epoch", "val_loss"}}
                with (directory / "history.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"epoch": trainer.current_epoch, **losses}) + "\n")

    torch.set_num_threads(config["threads"])
    pl.seed_everything(seed, workers=True)
    train_data = _features(used.loc[used["unit"].isin(train_units)], static)
    val_data = _features(used.loc[used["unit"].isin(val_units)], static)
    for data in (train_data, val_data):
        if not data.groupby("unit")["cycle"].diff().dropna().eq(1).all():
            raise ValueError("TFT requires consecutive cycles within each engine")
    multi = len(targets) > 1
    unknown = list(dict.fromkeys([*targets, *observed]))
    normalizer = MultiNormalizer([TorchNormalizer() for _ in targets]) if multi else TorchNormalizer()
    training = dataset(train_data, time_idx="cycle", target=targets if multi else targets[0],
                       group_ids=["unit"], max_encoder_length=encoder,
                       max_prediction_length=horizon, static_reals=static,
                       categorical_encoders={"unit": NaNLabelEncoder(add_nan=True, warn=False)},
                       time_varying_known_reals=["cycle"], time_varying_unknown_reals=unknown,
                       target_normalizer=normalizer, add_relative_time_idx=True)
    validation = dataset.from_dataset(training, val_data, predict=True)
    parameters = training.get_parameters()
    directory.mkdir()
    (directory / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    torch.save(parameters, directory / "preprocessing.pt")
    loss = MultiLoss([QuantileLoss() for _ in targets]) if multi else QuantileLoss()
    model = model_class.from_dataset(training, loss=loss, hidden_size=config["hidden_size"],
                                     attention_head_size=config["attention_head_size"],
                                     dropout=config["dropout"], learning_rate=config["learning_rate"],
                                     optimizer="adam")
    checkpoint = ModelCheckpoint(dirpath=directory, filename="epoch-{epoch}", monitor="val_loss",
                                 save_top_k=1, save_last=True)
    trainer = pl.Trainer(accelerator=config["accelerator"], devices=1, deterministic=True,
                         max_epochs=config["max_epochs"], logger=False, enable_progress_bar=False,
                         enable_model_summary=False, num_sanity_val_steps=0, gradient_clip_val=0.1,
                         limit_train_batches=config.get("limit_train_batches", 1.0),
                         limit_val_batches=config.get("limit_val_batches", 1.0),
                         callbacks=[EarlyStopping("val_loss", patience=config["patience"]),
                                    checkpoint, History()])
    batch = config["batch_size"]
    trainer.fit(model, training.to_dataloader(train=True, batch_size=batch),
                validation.to_dataloader(train=False, batch_size=batch),
                ckpt_path=str(resume) if resume else None, weights_only=False)
    best = Path(checkpoint.best_model_path) if checkpoint.best_model_path else None
    best_loss = float(checkpoint.best_model_score) if checkpoint.best_model_score is not None else None
    if resume is not None and (resume.parent / "best_validation.json").is_file():
        previous_best = resume.parent / "best.ckpt"
        previous_loss = json.loads((resume.parent / "best_validation.json").read_text(encoding="utf-8"))
        if previous_best.is_file() and (best_loss is None or previous_loss <= best_loss):
            best, best_loss = previous_best, previous_loss
    if best is None or not best.is_file():
        raise RuntimeError("TFT produced no validated checkpoint")
    shutil.copy2(best, directory / "best.ckpt")
    if best_loss is not None:
        (directory / "best_validation.json").write_text(json.dumps(best_loss), encoding="utf-8")
    if not (directory / "last.ckpt").is_file() and resume is not None:
        shutil.copy2(resume, directory / "last.ckpt")
    return TFTFit.load(directory, config["accelerator"])

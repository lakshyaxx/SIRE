"""C-MAPSS inputs for fixed-origin sensor forecasting."""
import numpy as np
import pandas as pd
import yaml

from pdm.common.paths import CONFIG_DIR
from pdm.data.loaders.cmapss_loader import SENSOR_COLUMNS


def read_settings(*parts: str) -> dict:
    """Load a repository YAML mapping."""
    with CONFIG_DIR.joinpath(*parts).open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError(f"Expected a YAML mapping in {'/'.join(parts)}")
    return config


def split_history(frame: pd.DataFrame, unit: int, targets: list[str],
                  horizon: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return one engine's observed prefix and untouched scoring suffix."""
    if not targets or len(set(targets)) != len(targets) or not set(targets) <= set(SENSOR_COLUMNS):
        raise ValueError("Choose distinct C-MAPSS sensor columns as targets")
    trajectory = frame.loc[frame["unit"] == unit].sort_values("cycle").set_index("cycle")
    if horizon < 2 or len(trajectory) - horizon < 20:
        raise ValueError("Need at least 20 observed cycles and a horizon of at least 2")
    if not np.all(np.diff(trajectory.index) == 1):
        raise ValueError("Engine cycles must be consecutive and unique")
    return trajectory.iloc[:-horizon], trajectory.iloc[-horizon:][targets]


def known_regressors(index: pd.Index, columns: list[str]) -> pd.DataFrame | None:
    """Build regressors computable from forecast-time information alone."""
    if len(set(columns)) != len(columns) or set(columns) - {"cycle", "log_cycle"}:
        raise ValueError("Only cycle and log_cycle are supported future-known regressors")
    if not columns:
        return None
    features = {"cycle": index.to_numpy(dtype=float) / 100.0, "log_cycle": np.log(index)}
    return pd.DataFrame({column: features[column] for column in columns}, index=index)

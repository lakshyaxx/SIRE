"""Load the configured sensor series and isolate generated experiment outputs."""
from pathlib import Path
from tempfile import mkdtemp

import pandas as pd
import yaml

from pdm.common.paths import CONFIG_DIR, resolve_path
from pdm.data.loaders.cmapss_loader import CMapssLoader


def load_sensor_series() -> pd.Series:
    """Load one sensor trajectory, sorted by cycle with a fresh row index."""
    with (CONFIG_DIR / "forecasting" / "sensor_experiment.yaml").open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    with (CONFIG_DIR / "data" / "cmapss.yaml").open(encoding="utf-8") as stream:
        data_config = yaml.safe_load(stream)
    data = CMapssLoader(resolve_path(data_config["raw_dir"])).load_train(config["subset"])
    sensor = config["sensor"]
    return (
        data.loc[data["unit"] == config["unit"]]
        .sort_values("cycle")[f"sensor_{sensor}"]
        .astype(float)
        .reset_index(drop=True)
        .rename(4 + sensor)
    )


def new_run_directory() -> Path:
    """Create a unique directory for one invocation's figures and metrics."""
    with (CONFIG_DIR / "forecasting" / "sensor_experiment.yaml").open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    runs_dir = resolve_path(config["runs_dir"])
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_dir = Path(mkdtemp(prefix="sensor-", dir=runs_dir))
    for folder in ("figures/forecasts", "figures/diagnostics", "figures/comparisons", "metrics"):
        (run_dir / folder).mkdir(parents=True)
    return run_dir

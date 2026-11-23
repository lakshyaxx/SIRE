"""Build piecewise linear RUL targets for C-MAPSS trajectories."""
import pandas as pd


def add_rul_labels(frame: pd.DataFrame, clip: int = 125) -> pd.DataFrame:
    """Add cycle-based RUL labels clipped to ``clip`` for complete train engines."""
    if clip <= 0:
        raise ValueError("clip must be positive")
    result = frame.copy()
    last_cycle = result.groupby("unit")["cycle"].transform("max")
    result["rul"] = (last_cycle - result["cycle"]).clip(upper=clip).astype("int64")
    return result


def add_test_rul_labels(frame: pd.DataFrame, final_rul: pd.Series, clip: int = 125) -> pd.DataFrame:
    """Add clipped test RUL labels using official RUL at each engine's final row."""
    result = frame.copy()
    final_cycle = result.groupby("unit")["cycle"].transform("max")
    result["rul"] = (result["unit"].map(final_rul) + final_cycle - result["cycle"]).clip(upper=clip).astype("int64")
    return result

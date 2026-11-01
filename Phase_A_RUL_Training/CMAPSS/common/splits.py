"""Deterministic train/validation splits grouped by engine id."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .config import cmapss_root


@dataclass(frozen=True)
class EngineSplit:
    """Engine ids assigned to train and validation partitions."""

    dataset: str
    train_units: tuple[int, ...]
    val_units: tuple[int, ...]
    seed: int
    val_fraction: float


def split_engine_ids(engine_ids: list[int] | tuple[int, ...], val_fraction: float = 0.2, seed: int = 42) -> tuple[list[int], list[int]]:
    """Split unique engine ids without allowing any engine into both sets."""
    ids = np.asarray(sorted({int(value) for value in engine_ids}), dtype=np.int64)
    if ids.size < 2:
        raise ValueError("at least two engines are required for a train/validation split")
    if not 0.0 < val_fraction < 1.0:
        raise ValueError("val_fraction must be between 0 and 1")
    n_val = min(max(int(round(ids.size * val_fraction)), 1), ids.size - 1)
    order = np.random.default_rng(seed).permutation(ids)
    val_ids = sorted(int(value) for value in order[:n_val])
    train_ids = sorted(int(value) for value in order[n_val:])
    return train_ids, val_ids


def _split_path(path: str | Path | None) -> Path:
    """Resolve the shared split-file path."""
    return Path(path) if path is not None else cmapss_root() / "results" / "splits.json"


def get_or_create_split(
    dataset: str,
    engine_ids: list[int] | tuple[int, ...],
    val_fraction: float = 0.2,
    seed: int = 42,
    path: str | Path | None = None,
) -> EngineSplit:
    """Load a compatible split or create and persist the deterministic split."""
    target = _split_path(path)
    normalized = dataset.upper()
    expected_ids = sorted({int(value) for value in engine_ids})
    if target.exists():
        payload = json.loads(target.read_text(encoding="utf-8"))
    else:
        payload = {"version": 1, "datasets": {}}
    entry = payload.setdefault("datasets", {}).get(normalized)
    if entry is not None:
        split = EngineSplit(
            dataset=normalized,
            train_units=tuple(int(value) for value in entry["train_units"]),
            val_units=tuple(int(value) for value in entry["val_units"]),
            seed=int(entry["seed"]),
            val_fraction=float(entry["val_fraction"]),
        )
        actual_ids = sorted((*split.train_units, *split.val_units))
        if set(split.train_units) & set(split.val_units):
            raise ValueError(f"Saved split for {normalized} contains overlapping engine ids")
        if actual_ids != expected_ids:
            raise ValueError(f"Saved split for {normalized} does not match current training engine ids")
        if split.seed != seed or not np.isclose(split.val_fraction, val_fraction):
            raise ValueError(f"Saved split for {normalized} uses seed/fraction {split.seed}/{split.val_fraction}, requested {seed}/{val_fraction}")
        return split

    train_ids, val_ids = split_engine_ids(expected_ids, val_fraction=val_fraction, seed=seed)
    split = EngineSplit(normalized, tuple(train_ids), tuple(val_ids), seed, val_fraction)
    payload.setdefault("datasets", {})[normalized] = {
        "train_units": list(split.train_units),
        "val_units": list(split.val_units),
        "seed": seed,
        "val_fraction": val_fraction,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return split


def split_to_dict(split: EngineSplit) -> dict[str, object]:
    """Serialize a split using JSON-compatible lists."""
    result = asdict(split)
    result["train_units"] = list(split.train_units)
    result["val_units"] = list(split.val_units)
    return result

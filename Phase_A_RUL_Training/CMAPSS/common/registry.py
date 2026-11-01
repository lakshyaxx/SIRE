"""Read and write the Phase A predictor model registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import cmapss_root


def registry_path(path: str | Path | None = None) -> Path:
    """Resolve the CMAPSS model registry file."""
    return Path(path) if path is not None else cmapss_root() / "model_registry.json"


def write_registry(registry: dict[str, Any], path: str | Path | None = None) -> Path:
    """Write a JSON-compatible registry atomically."""
    target = registry_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def read_registry(path: str | Path | None = None) -> dict[str, Any]:
    """Read and validate that the registry root is a JSON object."""
    target = registry_path(path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Registry root in {target} must be a JSON object")
    return payload

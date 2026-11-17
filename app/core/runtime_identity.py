"""Identify the source and frontend loaded when a local app instance was created."""

import hashlib
from pathlib import Path


def source_identity(root: Path, frontend: Path) -> str:
    """Hash application/config source plus the served index, excluding data and weights."""
    digest = hashlib.sha256()
    paths = sorted((root / "app").rglob("*.py")) + sorted(
        (root / "config").glob("*.yaml")
    )
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0" + path.read_bytes() + b"\0")
    index = frontend / "index.html"
    if index.is_file():
        digest.update(b"frontend-index\0" + index.read_bytes())
    return digest.hexdigest()

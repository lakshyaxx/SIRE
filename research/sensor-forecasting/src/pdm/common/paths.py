"""Single source of truth for repository paths."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
CONFIG_DIR = ROOT / "configs"
DOCS_DIR = ROOT / "docs"


def resolve_path(path: str | Path) -> Path:
    """Resolve a configured relative path against the repository root."""
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate

"""Generate labeled synthetic data without touching user uploads or preserved model artifacts."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core.config import STATE
from app.simulation.generator import seed_scenarios


def main() -> None:
    """Seed an idempotent synthetic-only directory; use a new path for a new seed/version."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--directory", type=Path, default=STATE / "scenarios")
    args = parser.parse_args()
    print(json.dumps(seed_scenarios(args.directory.resolve(), args.seed), indent=2))


if __name__ == "__main__":
    main()

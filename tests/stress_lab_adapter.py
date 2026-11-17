"""CLI entry point for real SIRE ASGI stress assessment; fixture/evaluator data never becomes code."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.stress_lab.runner import main

if __name__ == "__main__":
    main()

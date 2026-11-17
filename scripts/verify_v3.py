"""Bounded V3 regression/format/build verification with an optional fresh full native audit."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Stop on an actual failing command; do not replace failures with historical counts."""
    p = argparse.ArgumentParser()
    p.add_argument("--full-model-audit", action="store_true")
    args = p.parse_args()
    commands = [
        [sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"],
        [sys.executable, "-m", "ruff", "check", "app", "scripts", "tests"],
        [sys.executable, "-m", "black", "--check", "app", "scripts", "tests"],
        [sys.executable, "scripts/verify_parity.py"],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
    import shutil

    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise SystemExit("Node/npm unavailable; frontend build not verified.")
    subprocess.run(
        [npm, "run", "build", "--", "--outDir", "dist-v3"], cwd=ROOT / "web", check=True
    )
    if args.full_model_audit:
        subprocess.run(
            [sys.executable, "scripts/audit_models.py"], cwd=ROOT, check=True
        )


if __name__ == "__main__":
    main()

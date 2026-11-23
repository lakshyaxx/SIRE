"""Run the configured ARIMAX sensor forecasting benchmark."""
import sys

from pdm.forecasting.benchmark import main


if __name__ == "__main__":
    raise SystemExit(main(["--models", "arimax", *sys.argv[1:]]))

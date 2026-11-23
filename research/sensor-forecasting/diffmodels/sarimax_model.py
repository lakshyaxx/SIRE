"""Run the configured SARIMAX sensor forecasting benchmark."""
import sys

from pdm.forecasting.benchmark import main


if __name__ == "__main__":
    raise SystemExit(main(["--models", "sarimax", *sys.argv[1:]]))

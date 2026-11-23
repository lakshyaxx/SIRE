"""Run the configured Holt-Winters sensor forecasting benchmark."""
import sys

from pdm.forecasting.benchmark import main


if __name__ == "__main__":
    raise SystemExit(main(["--models", "holt_winters", *sys.argv[1:]]))

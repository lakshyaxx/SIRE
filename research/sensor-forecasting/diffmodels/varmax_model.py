"""Run the configured VARMAX sensor forecasting benchmark."""
import sys

from pdm.forecasting.benchmark import main


if __name__ == "__main__":
    raise SystemExit(main(["--models", "varmax", *sys.argv[1:]]))

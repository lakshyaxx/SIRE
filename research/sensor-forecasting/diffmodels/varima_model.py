"""Run the configured VARIMA sensor forecasting benchmark."""
import sys

from pdm.forecasting.benchmark import main


if __name__ == "__main__":
    raise SystemExit(main(["--models", "varima", *sys.argv[1:]]))

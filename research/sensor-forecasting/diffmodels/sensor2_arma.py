"""Run the configured ARMA sensor forecasting benchmark."""
import sys

from pdm.forecasting.benchmark import main


if __name__ == "__main__":
    raise SystemExit(main(["--models", "arma", *sys.argv[1:]]))

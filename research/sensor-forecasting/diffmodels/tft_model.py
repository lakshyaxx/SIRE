"""Run the configured TFT sensor forecasting benchmark."""
import sys

from pdm.forecasting.benchmark import main


if __name__ == "__main__":
    options = sys.argv[1:]
    if "--full-tft" not in options and "--tft-smoke" not in options:
        options = ["--tft-smoke", *options]
    raise SystemExit(main(["--models", "tft", *options]))

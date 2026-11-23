import pandas as pd
from statsmodels.tsa.stattools import adfuller, kpss
import matplotlib.pyplot as plt

from pdm.forecasting.sensor_experiment import load_sensor_series, new_run_directory


def main() -> None:
    """Run the stationarity analysis experiment."""
    series = load_sensor_series()

    # Original and first-differenced series
    original = series
    differenced = series.diff().dropna()

    def run_tests(name, values):
        adf_stat, adf_p, *_ = adfuller(values)
        kpss_stat, kpss_p, *_ = kpss(values, regression="c", nlags="auto")

        print(f"\n{name}")
        print(f"ADF statistic: {adf_stat:.4f}")
        print(f"ADF p-value:   {adf_p:.6f}")
        print(f"KPSS statistic: {kpss_stat:.4f}")
        print(f"KPSS p-value:   {kpss_p:.6f}")

        return {
            "Series": name,
            "ADF statistic": adf_stat,
            "ADF p-value": adf_p,
            "KPSS statistic": kpss_stat,
            "KPSS p-value": kpss_p
        }

    results = [
        run_tests("Original sensor_2", original),
        run_tests("First-differenced sensor_2", differenced)
    ]

    run_dir = new_run_directory()
    pd.DataFrame(results).to_csv(run_dir / "metrics/stationarity_results.csv", index=False)
    print("\nSaved stationarity_results.csv")

    # Visualize differencing
    fig, axes = plt.subplots(2, 1, figsize=(11, 7))

    axes[0].plot(original)
    axes[0].set_title("Original Sensor 2 Series")
    axes[0].set_xlabel("Cycle")
    axes[0].set_ylabel("Sensor reading")

    axes[1].plot(differenced)
    axes[1].set_title("First-Differenced Sensor 2 Series")
    axes[1].set_xlabel("Cycle")
    axes[1].set_ylabel("Change in reading")

    plt.tight_layout()
    plt.savefig(run_dir / "figures/diagnostics/stationarity_plots.png", dpi=150)
    plt.show()
    print(f"Output directory: {run_dir}")


if __name__ == "__main__":
    main()

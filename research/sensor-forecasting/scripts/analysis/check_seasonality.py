import matplotlib.pyplot as plt
from statsmodels.graphics.tsaplots import plot_acf

from pdm.forecasting.sensor_experiment import load_sensor_series, new_run_directory


def main() -> None:
    """Run the check seasonality experiment."""
    series = load_sensor_series()

    # First difference to reduce the trend
    differenced = series.diff().dropna()

    # Inspect autocorrelation across lags
    fig, axes = plt.subplots(2, 1, figsize=(11, 8))

    plot_acf(series, lags=40, ax=axes[0])
    axes[0].set_title("ACF: Original Sensor 2 Series")

    plot_acf(differenced, lags=40, ax=axes[1])
    axes[1].set_title("ACF: First-Differenced Sensor 2 Series")

    plt.tight_layout()
    run_dir = new_run_directory()
    plt.savefig(run_dir / "figures/diagnostics/sensor2_acf_analysis.png", dpi=150)
    plt.show()

    print("Saved: sensor2_acf_analysis.png")
    print("Inspect whether meaningful repeating peaks appear at regular lags.")


    print(f"Output directory: {run_dir}")


if __name__ == "__main__":
    main()

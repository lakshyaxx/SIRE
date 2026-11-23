import numpy as np
import matplotlib.pyplot as plt

from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.graphics.tsaplots import plot_acf
from statsmodels.stats.diagnostic import acorr_ljungbox
from sklearn.metrics import mean_absolute_error, mean_squared_error

from pdm.forecasting.sensor_experiment import load_sensor_series, new_run_directory


def main() -> None:
    """Run the residual analysis experiment."""
    series = load_sensor_series()

    # Chronological 80/20 split
    split = int(len(series) * 0.8)
    train = series.iloc[:split]
    test = series.iloc[split:]

    # Fit Holt Linear on training data
    model = ExponentialSmoothing(
        train,
        trend="add",
        seasonal=None
    ).fit(optimized=True)

    forecast = np.asarray(model.forecast(len(test)))
    actual = test.to_numpy()

    # Forecast errors: actual minus predicted
    residuals = actual - forecast

    mae = mean_absolute_error(actual, forecast)
    rmse = np.sqrt(mean_squared_error(actual, forecast))

    print("HOLT LINEAR RESIDUAL ANALYSIS")
    print(f"MAE:  {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")
    print(f"Mean residual: {np.mean(residuals):.4f}")
    print(f"Residual standard deviation: {np.std(residuals, ddof=1):.4f}")

    # Ljung-Box test on forecast errors
    # Interpret cautiously: errors come from a fixed-horizon forecast.
    lb = acorr_ljungbox(
        residuals,
        lags=[min(10, len(residuals) // 5)],
        return_df=True
    )

    print("\nLjung-Box test on forecast errors:")
    print(lb.round(4).to_string())

    # Plot residuals and their autocorrelation
    fig, axes = plt.subplots(2, 1, figsize=(11, 7))

    axes[0].plot(test.index, residuals, marker="o", markersize=3)
    axes[0].axhline(0, color="black", linestyle="--")
    axes[0].set_title("Holt Linear: Test Forecast Errors")
    axes[0].set_xlabel("Cycle")
    axes[0].set_ylabel("Actual - Forecast")

    plot_acf(residuals, lags=10, ax=axes[1])
    axes[1].set_title("ACF of Holt Linear Test Forecast Errors")

    plt.tight_layout()
    run_dir = new_run_directory()
    plt.savefig(run_dir / "figures/diagnostics/holt_residual_analysis.png", dpi=150)
    plt.show()

    print("\nSaved: holt_residual_analysis.png")

    print(f"Output directory: {run_dir}")


if __name__ == "__main__":
    main()

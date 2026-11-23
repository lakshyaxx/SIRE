import numpy as np
import matplotlib.pyplot as plt

from statsmodels.tsa.holtwinters import ExponentialSmoothing
from sklearn.metrics import mean_absolute_error, mean_squared_error

from pdm.forecasting.sensor_experiment import load_sensor_series, new_run_directory


def main() -> None:
    """Run the plot holt winters experiment."""
    series = load_sensor_series()

    split = int(len(series) * 0.8)
    train = series.iloc[:split]
    test = series.iloc[split:]

    model = ExponentialSmoothing(
        train,
        trend="add",
        seasonal=None
    ).fit(optimized=True)

    forecast = model.forecast(len(test))

    mae = mean_absolute_error(test, forecast)
    rmse = np.sqrt(mean_squared_error(test, forecast))

    plt.figure(figsize=(12, 5))
    plt.plot(train.index, train, label="Training data")
    plt.plot(test.index, test, label="Actual test values")
    plt.plot(test.index, forecast, label="Holt Linear forecast")

    plt.title("NASA C-MAPSS FD001: Holt Linear Forecast")
    plt.xlabel("Cycle")
    plt.ylabel("Sensor 2 reading")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    run_dir = new_run_directory()
    plt.savefig(run_dir / "figures/forecasts/sensor2_holt_forecast.png", dpi=150)
    plt.show()

    print(f"Test MAE: {mae:.4f}")
    print(f"Test RMSE: {rmse:.4f}")
    print("Plot saved as sensor2_holt_forecast.png")
    print(f"Output directory: {run_dir}")


if __name__ == "__main__":
    main()

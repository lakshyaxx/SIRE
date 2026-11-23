import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.arima.model import ARIMA
from sklearn.metrics import mean_absolute_error, mean_squared_error

from pdm.forecasting.sensor_experiment import load_sensor_series, new_run_directory


def main() -> None:
    """Run the ma model experiment."""
    series = load_sensor_series()

    # Chronological 80/20 split
    split = int(len(series) * 0.8)
    train = series.iloc[:split]
    test = series.iloc[split:]

    # Train MA(1): ARIMA(p=0, d=0, q=1)
    model = ARIMA(train, order=(0, 0, 1)).fit()
    forecast = model.forecast(steps=len(test))

    # Evaluate
    mae = mean_absolute_error(test, forecast)
    rmse = np.sqrt(mean_squared_error(test, forecast))

    print("Model: MA(1)")
    print(f"MAE:  {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")

    # Plot
    plt.figure(figsize=(12, 5))
    plt.plot(train.index, train, label="Training data")
    plt.plot(test.index, test, label="Actual test values")
    plt.plot(test.index, forecast, label="MA(1) forecast")

    plt.title("NASA C-MAPSS FD001: MA(1) Forecast")
    plt.xlabel("Cycle")
    plt.ylabel("Sensor 2 reading")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    run_dir = new_run_directory()
    plt.savefig(run_dir / "figures/forecasts/sensor2_ma_forecast.png", dpi=150)
    plt.show()
    print(f"Output directory: {run_dir}")


if __name__ == "__main__":
    main()

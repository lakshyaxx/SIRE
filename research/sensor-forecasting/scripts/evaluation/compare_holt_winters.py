import numpy as np
import warnings

from statsmodels.tsa.holtwinters import ExponentialSmoothing
from sklearn.metrics import mean_absolute_error, mean_squared_error

from pdm.forecasting.sensor_experiment import load_sensor_series


def main() -> None:
    """Run the compare holt winters experiment."""
    warnings.filterwarnings("ignore")

    series = load_sensor_series()

    split = int(len(series) * 0.8)
    train = series.iloc[:split]
    test = series.iloc[split:]

    models = {
        "Simple Exponential": ExponentialSmoothing(
            train, trend=None, seasonal=None
        ),
        "Holt Linear": ExponentialSmoothing(
            train, trend="add", seasonal=None
        ),
    }

    print(f"{'Model':<22}{'MAE':>10}{'RMSE':>10}")

    for name, model in models.items():
        fitted = model.fit(optimized=True)
        forecast = fitted.forecast(len(test))

        mae = mean_absolute_error(test, forecast)
        rmse = np.sqrt(mean_squared_error(test, forecast))

        print(f"{name:<22}{mae:>10.4f}{rmse:>10.4f}")


if __name__ == "__main__":
    main()

import numpy as np
from statsmodels.tsa.arima.model import ARIMA
from sklearn.metrics import mean_absolute_error, mean_squared_error

from pdm.forecasting.sensor_experiment import load_sensor_series


def main() -> None:
    """Run the compare arima experiment."""
    series = load_sensor_series()

    # Chronological 80/20 split
    split = int(len(series) * 0.8)
    train = series.iloc[:split]
    test = series.iloc[split:]

    orders = [
        (0, 1, 1),
        (1, 1, 0),
        (1, 1, 1),
        (2, 1, 1),
        (1, 1, 2),
    ]

    print(f"Training observations: {len(train)}")
    print(f"Testing observations:  {len(test)}")
    print(f"\n{'ARIMA order':<15}{'MAE':>10}{'RMSE':>10}{'AIC':>12}")

    for order in orders:
        try:
            model = ARIMA(train, order=order).fit()
            forecast = model.forecast(steps=len(test))

            mae = mean_absolute_error(test, forecast)
            rmse = np.sqrt(mean_squared_error(test, forecast))

            print(f"{str(order):<15}{mae:>10.4f}{rmse:>10.4f}{model.aic:>12.3f}")

        except Exception as error:
            print(f"{str(order):<15}Failed: {error}")


if __name__ == "__main__":
    main()

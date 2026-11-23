import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.metrics import mean_absolute_error, mean_squared_error

from pdm.forecasting.sensor_experiment import load_sensor_series


def main() -> None:
    """Run the test sarima experiment."""
    series = load_sensor_series()

    split = int(len(series) * 0.8)
    train = series.iloc[:split]
    test = series.iloc[split:]

    # Illustrative seasonal period of 10 cycles.
    # Compare against the non-seasonal baseline; this period
    # is a hypothesis, not an established property of the data.
    model = SARIMAX(
        train,
        order=(1, 1, 0),
        seasonal_order=(1, 0, 0, 10),
        enforce_stationarity=False,
        enforce_invertibility=False
    ).fit(disp=False)

    forecast = model.forecast(steps=len(test))

    mae = mean_absolute_error(test, forecast)
    rmse = np.sqrt(mean_squared_error(test, forecast))

    print("SARIMA(1,1,0)(1,0,0,10)")
    print(f"MAE:  {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")
    print(f"AIC:  {model.aic:.3f}")


if __name__ == "__main__":
    main()

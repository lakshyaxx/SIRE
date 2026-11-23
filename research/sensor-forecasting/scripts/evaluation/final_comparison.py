import warnings
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from statsmodels.tsa.ar_model import AutoReg
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from sklearn.metrics import mean_absolute_error, mean_squared_error

from pdm.forecasting.sensor_experiment import load_sensor_series, new_run_directory


def main() -> None:
    """Run the final comparison experiment."""
    warnings.filterwarnings("ignore")

    series = load_sensor_series()
    series.name = "sensor_2"

    # 3. Chronological train-test split (80:20)
    split = int(len(series) * 0.8)
    train = series.iloc[:split]
    test = series.iloc[split:]

    results = []
    forecasts = {}

    def evaluate(name, forecast, aic=np.nan):
        forecast = np.asarray(forecast, dtype=float)

        mae = mean_absolute_error(test, forecast)
        rmse = np.sqrt(mean_squared_error(test, forecast))

        # MAPE expressed as a percentage
        actual = test.to_numpy()
        nonzero = actual != 0
        mape = np.mean(
            np.abs((actual[nonzero] - forecast[nonzero]) / actual[nonzero])
        ) * 100

        results.append({
            "Model": name,
            "MAE": mae,
            "RMSE": rmse,
            "MAPE (%)": mape,
            "AIC": aic
        })
        forecasts[name] = forecast

    # 4. AR(1)
    model = AutoReg(train, lags=1, trend="c").fit()
    evaluate("AR(1)", model.forecast(len(test)))

    # 5. MA(1)
    model = ARIMA(train, order=(0, 0, 1)).fit()
    evaluate("MA(1)", model.forecast(len(test)), model.aic)

    # 6. ARIMA configurations
    for order in [
        (0, 1, 1),
        (1, 1, 0),
        (1, 1, 1),
        (2, 1, 1),
        (1, 1, 2)
    ]:
        model = ARIMA(train, order=order).fit()
        evaluate(
            f"ARIMA{order}",
            model.forecast(len(test)),
            model.aic
        )

    # 7. Simple Exponential Smoothing
    model = ExponentialSmoothing(
        train, trend=None, seasonal=None
    ).fit(optimized=True)
    evaluate("Simple Exponential Smoothing", model.forecast(len(test)))

    # 8. Holt Linear
    model = ExponentialSmoothing(
        train, trend="add", seasonal=None
    ).fit(optimized=True)
    evaluate("Holt Linear", model.forecast(len(test)))

    # 9. SARIMA
    model = SARIMAX(
        train,
        order=(1, 1, 0),
        seasonal_order=(1, 0, 0, 10),
        enforce_stationarity=False,
        enforce_invertibility=False
    ).fit(disp=False)
    evaluate(
        "SARIMA(1,1,0)(1,0,0,10)",
        model.forecast(len(test)),
        model.aic
    )

    # 10. Save comparison table
    results_df = pd.DataFrame(results).sort_values("RMSE")
    run_dir = new_run_directory()
    results_df.to_csv(run_dir / "metrics/model_comparison_results.csv", index=False)

    print("\nMODEL COMPARISON — LOWER ERRORS ARE BETTER")
    print(results_df.round(4).to_string(index=False))
    print("\nSaved: model_comparison_results.csv")

    # 11. Plot RMSE comparison
    plt.figure(figsize=(13, 6))
    plt.bar(results_df["Model"], results_df["RMSE"])
    plt.title("Forecast Model Comparison — Test RMSE")
    plt.xlabel("Model")
    plt.ylabel("RMSE (lower is better)")
    plt.xticks(rotation=45, ha="right")
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(run_dir / "figures/comparisons/model_comparison_rmse.png", dpi=150)
    plt.show()

    print("Saved: model_comparison_rmse.png")

    # 12. Plot actual vs forecast for the best model by RMSE
    best_name = results_df.iloc[0]["Model"]
    best_forecast = forecasts[best_name]

    plt.figure(figsize=(12, 5))
    plt.plot(train.index, train, label="Training data")
    plt.plot(test.index, test, label="Actual test values")
    plt.plot(test.index, best_forecast, label=f"{best_name} forecast")
    plt.title(f"Best Model by Test RMSE: {best_name}")
    plt.xlabel("Cycle")
    plt.ylabel("Sensor 2 reading")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(run_dir / "figures/forecasts/best_model_forecast.png", dpi=150)
    plt.show()

    print(f"Best model by RMSE: {best_name}")
    print("Saved: best_model_forecast.png")
    print(f"Output directory: {run_dir}")


if __name__ == "__main__":
    main()

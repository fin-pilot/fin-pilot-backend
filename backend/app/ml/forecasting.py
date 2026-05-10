import pandas as pd

# import statsmodels.api as sm


def run_sarima_forecast(history_df: pd.DataFrame, steps: int):
    # TODO implement method
    last_date = history_df["ds"].max()
    forecast_dates = pd.date_range(last_date, periods=steps + 1, freq="D")[1:]

    return [
        {"date": d.date(), "amount": 500.0 + (i * 10.5)}
        for i, d in enumerate(forecast_dates)
    ]

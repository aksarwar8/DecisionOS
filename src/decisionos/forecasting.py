
import pandas as pd


def naive_forecast(daily_total_sales):
    """Predict each day's sales using the previous day's actual sales."""

    forecast = daily_total_sales.shift(1)

    return forecast



def moving_average_forecast(daily_total_sales, window=7):
    """Forecast using the average sales of the previous 7 days."""

    forecast = daily_total_sales.shift(1).rolling(window=window).mean()

    return forecast

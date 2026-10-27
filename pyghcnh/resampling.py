import pandas as pd

from pyghcnh.degree_days import DegreeDayMethod, calculate_cdd, calculate_hdd


def to_daily(
    df: pd.DataFrame,
    hdd_threshold: float = 18.0,
    cdd_threshold: float = 18.0,
    method: DegreeDayMethod = DegreeDayMethod.MEAN,
    tz: str | None = None,
) -> pd.DataFrame:
    """Convert the hourly data to daily data, with Heating and Cooling Degree Days.

    Args:
        df (pd.DataFrame): the hourly data, as returned by GHCNh.get_data or GHCNh.get_period_of_record
        hdd_threshold (float, optional): the HDD base temperature, in °C
        cdd_threshold (float, optional): the CDD base temperature, in °C
        method (DegreeDayMethod, optional): which daily temperature the Degree Days use: the daily mean,
            or the mean of the daily min and max (Météo-France)
        tz (str, optional): the time zone used to split the days, eg 'Europe/Paris'. Defaults to UTC

    Returns:
        df_daily (pd.DataFrame): daily data, with 'temperature_min', 'temperature_max', 'hdd' and 'cdd' columns

    """
    if tz is not None:
        df = df.tz_convert(tz)

    resampled = df.resample("D")
    # wind_direction is not averaged: the mean of compass directions is meaningless (359° and 1° give 180°)
    df_daily = resampled.agg(
        {
            "temperature": "mean",
            "dew_point_temperature": "mean",
            "relative_humidity": "mean",
            "wet_bulb_temperature": "mean",
            "wind_speed": "mean",
            "precipitation_3_hour": "mean",
            "precipitation_6_hour": "mean",
        }
    )
    # min_count=1 so a day without any report is NaN, not 0
    df_daily["precipitation"] = resampled["precipitation"].sum(min_count=1)
    df_daily["temperature_min"] = resampled["temperature"].min()
    df_daily["temperature_max"] = resampled["temperature"].max()

    if method == DegreeDayMethod.MEAN:
        daily_temp = df_daily["temperature"]
    elif method == DegreeDayMethod.METEOFRANCE:
        daily_temp = (df_daily["temperature_min"] + df_daily["temperature_max"]) / 2.0
    else:
        raise ValueError(f"Unknown method {method}")

    df_daily["hdd"] = calculate_hdd(daily_temp, hdd_threshold=hdd_threshold)
    df_daily["cdd"] = calculate_cdd(daily_temp, cdd_threshold=cdd_threshold)

    return df_daily


def to_monthly(df_daily: pd.DataFrame) -> pd.DataFrame:
    """Convert the daily data to monthly data.

    Args:
        df_daily (pd.DataFrame): the daily data, as returned by to_daily. Its time zone is kept

    Returns:
        df_monthly (pd.DataFrame): monthly data, indexed by the start of the month. 'temperature_min' and
            'temperature_max' are the extremes of the month, 'precipitation', 'hdd' and 'cdd' are monthly sums,
            'n_days' is the number of days with temperature data, the other columns are means

    """
    resampled = df_daily.resample("MS")
    df_monthly = resampled.agg(
        {
            "temperature": "mean",
            "dew_point_temperature": "mean",
            "relative_humidity": "mean",
            "wet_bulb_temperature": "mean",
            "wind_speed": "mean",
            "precipitation_3_hour": "mean",
            "precipitation_6_hour": "mean",
            "temperature_min": "min",
            "temperature_max": "max",
        }
    )
    # min_count=1 so a month without any data is NaN, not 0
    for col in ("precipitation", "hdd", "cdd"):
        df_monthly[col] = resampled[col].sum(min_count=1)
    # Sums are lower for a month with missing days, so keep track of them
    df_monthly["n_days"] = resampled["temperature"].count()

    return df_monthly

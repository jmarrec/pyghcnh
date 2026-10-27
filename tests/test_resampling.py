import math

import pandas as pd
import pytest

from pyghcnh.degree_days import DegreeDayMethod, calculate_cdd, calculate_hdd
from pyghcnh.GHCNh import GHCNh

NAN = float("nan")


def _hourly(timestamps: list[str], temperatures: list[float], precipitation: list[float] | None = None) -> pd.DataFrame:
    """Build hourly data shaped like the output of GHCNh.get_data, with a UTC index."""
    n = len(timestamps)
    df = pd.DataFrame(
        {
            "temperature": temperatures,
            "dew_point_temperature": [5.0] * n,
            "relative_humidity": [80.0] * n,
            "wet_bulb_temperature": [7.0] * n,
            "wind_direction": [180.0] * n,
            "wind_speed": [3.0] * n,
            "precipitation": precipitation if precipitation is not None else [NAN] * n,
            "precipitation_3_hour": [NAN] * n,
            "precipitation_6_hour": [NAN] * n,
        },
        index=pd.DatetimeIndex(timestamps, tz="UTC", name="DATE"),
    )
    return df


def _skewed_day_then_empty_day() -> pd.DataFrame:
    """Jan 1: 23 hours at 10°C and one at 30°C, with 3 mm of rain. Jan 2: reports, but no temperature nor rain."""
    day1 = [f"2026-01-01T{h:02d}:00:00" for h in range(24)]
    day2 = [f"2026-01-02T{h:02d}:00:00" for h in range(24)]
    temperatures = [10.0] * 23 + [30.0] + [NAN] * 24
    precipitation = [1.0, 2.0] + [NAN] * 46
    return _hourly(day1 + day2, temperatures, precipitation)


def test_to_daily_mean():
    df_daily = GHCNh.to_daily(_skewed_day_then_empty_day())

    assert len(df_daily) == 2
    day1 = df_daily.iloc[0]
    expected_mean = (23 * 10.0 + 30.0) / 24
    assert day1["temperature"] == pytest.approx(expected_mean)
    assert day1["temperature_min"] == 10.0
    assert day1["temperature_max"] == 30.0
    assert day1["hdd"] == pytest.approx(calculate_hdd(expected_mean))
    assert day1["cdd"] == 0.0
    assert day1["precipitation"] == 3.0

    assert "wind_direction" not in df_daily.columns


def test_to_daily_meteofrance():
    df_daily = GHCNh.to_daily(_skewed_day_then_empty_day(), method=DegreeDayMethod.METEOFRANCE)

    day1 = df_daily.iloc[0]
    # (10 + 30) / 2 = 20°C: no heating, unlike with the daily mean of ~10.8°C
    assert day1["hdd"] == 0.0
    assert day1["cdd"] == pytest.approx(calculate_cdd(20.0))


def test_to_daily_thresholds():
    df_daily = GHCNh.to_daily(_skewed_day_then_empty_day(), hdd_threshold=15.0, cdd_threshold=10.0)

    day1 = df_daily.iloc[0]
    expected_mean = (23 * 10.0 + 30.0) / 24
    assert day1["hdd"] == pytest.approx(15.0 - expected_mean)
    assert day1["cdd"] == pytest.approx(expected_mean - 10.0)


def test_to_daily_missing_day_is_nan():
    df_daily = GHCNh.to_daily(_skewed_day_then_empty_day())

    day2 = df_daily.iloc[1]
    assert math.isnan(day2["temperature"])
    assert math.isnan(day2["hdd"])
    assert math.isnan(day2["cdd"])
    assert math.isnan(day2["precipitation"])
    # Other variables are still there
    assert day2["wind_speed"] == 3.0


def test_to_daily_tz():
    # 23:00 and 23:30 UTC on Jan 1, but 00:00 and 00:30 on Jan 2 in Paris (UTC+1 in winter)
    df = _hourly(["2026-01-01T22:00:00", "2026-01-01T23:00:00", "2026-01-01T23:30:00"], [10.0, 20.0, 30.0])

    df_utc = GHCNh.to_daily(df)
    assert len(df_utc) == 1
    assert df_utc["temperature"].iloc[0] == pytest.approx(20.0)

    df_paris = GHCNh.to_daily(df, tz="Europe/Paris")
    assert str(df_paris.index.tz) == "Europe/Paris"
    assert df_paris.index[0] == pd.Timestamp("2026-01-01", tz="Europe/Paris")
    assert df_paris["temperature"].tolist() == pytest.approx([10.0, 25.0])


def test_to_monthly():
    # Jan 1 at 10°C with 3 mm of rain, Jan 2 at 20°C, nothing in February, Mar 1 at 5°C
    timestamps = ["2026-01-01T12:00:00", "2026-01-01T13:00:00", "2026-01-02T12:00:00", "2026-03-01T12:00:00"]
    df = _hourly(timestamps, [10.0, 10.0, 20.0, 5.0], precipitation=[1.0, 2.0, NAN, NAN])
    df_daily = GHCNh.to_daily(df)
    df_monthly = GHCNh.to_monthly(df_daily)

    assert df_monthly.index.tolist() == [
        pd.Timestamp("2026-01-01", tz="UTC"),
        pd.Timestamp("2026-02-01", tz="UTC"),
        pd.Timestamp("2026-03-01", tz="UTC"),
    ]

    jan = df_monthly.iloc[0]
    assert jan["hdd"] == pytest.approx(df_daily.loc["2026-01", "hdd"].sum())
    assert jan["hdd"] == pytest.approx(8.0)
    assert jan["cdd"] == pytest.approx(2.0)
    assert jan["precipitation"] == 3.0
    assert jan["temperature"] == pytest.approx(15.0)
    assert jan["temperature_min"] == 10.0
    assert jan["temperature_max"] == 20.0
    # Only 2 of the 31 days of January have data
    assert jan["n_days"] == 2

    feb = df_monthly.iloc[1]
    assert math.isnan(feb["hdd"])
    assert math.isnan(feb["cdd"])
    assert math.isnan(feb["precipitation"])
    assert feb["n_days"] == 0

    mar = df_monthly.iloc[2]
    assert mar["hdd"] == pytest.approx(13.0)
    assert mar["n_days"] == 1

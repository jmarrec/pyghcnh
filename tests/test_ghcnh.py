import math

import pandas as pd
import pytest

from pyghcnh.GHCNh import GHCNh

# A few rows from the real ghcnh-station-list.csv
STATION_LIST_CSV = """GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE
ACL000BARA9,17.591,-61.821,5.0,TX,BARBUDA,,,,,AG
ASN00072059,-36.0667,146.9333,182.9,,ALBURY GRAMMAR SCHOOL,,,,,AU
FRI0000LFRH,47.7606,-3.44,48.8,,LANN BIHOUE,,,,LFRH,FR
FRU56121004,47.745,-3.362,8.0,,LORIENT STATION AEROLOGIQUE,,,,,FR
"""


@pytest.fixture
def ghcnh(tmp_path):
    """Return a GHCNh using a small, freshly written station list, so nothing gets downloaded."""
    station_list_path = tmp_path / "ghcnh-station-list.csv"
    station_list_path.write_text(STATION_LIST_CSV)
    return GHCNh(ghcnh_stationlist_path=station_list_path)


def test_haversine_distance():
    assert GHCNh.haversine_distance(47.76, -3.44, 47.76, -3.44) == 0.0
    # Paris to London is about 343.5 km
    assert GHCNh.haversine_distance(48.8566, 2.3522, 51.5074, -0.1278) == pytest.approx(343.5, abs=1.0)


def test_clean_data():
    df = pd.DataFrame(
        {
            "DATE": ["2026-01-01T00:00:00", "2026-01-01T00:30:00", "2026-01-01T01:00:00"],
            "temperature": [-1.0, -2.0, -2.0],
            "relative_humidity": ["86", "93", None],
            "wind_direction": ["040", "000", "999"],
        }
    )
    df = GHCNh._clean_data(df)

    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) == "UTC"
    assert df.index[1] == pd.Timestamp("2026-01-01T00:30:00", tz="UTC")

    assert pd.api.types.is_numeric_dtype(df["relative_humidity"])
    assert df["relative_humidity"].iloc[0] == 86
    assert math.isnan(df["relative_humidity"].iloc[2])

    assert pd.api.types.is_numeric_dtype(df["wind_direction"])
    assert df["wind_direction"].iloc[0] == 40
    # 000 is calm, 999 is not a valid direction
    assert df["wind_direction"].iloc[1] == 0
    assert math.isnan(df["wind_direction"].iloc[2])


def test_closest_weather_stations(ghcnh):
    assert len(ghcnh.df_stations) == 4

    df = ghcnh.closest_weather_stations(lat=47.76, lon=-3.43, n=2)
    assert df.index.tolist() == ["FRI0000LFRH", "FRU56121004"]
    assert df["distance"].is_monotonic_increasing
    assert df["distance"].iloc[0] < 1.0


@pytest.mark.network
def test_get_data_network(ghcnh):
    df = ghcnh.get_data("FRI0000LFRH", start_year=2026, end_year=2026)

    assert not df.empty
    assert df.index.min() >= pd.Timestamp("2026-01-01", tz="UTC")
    assert set(df.columns) == set(GHCNh.KEPT_COLS) - {"DATE"}
    assert pd.api.types.is_numeric_dtype(df["relative_humidity"])
    assert pd.api.types.is_numeric_dtype(df["wind_direction"])

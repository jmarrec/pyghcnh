import math
import os
import time

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


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, content: bytes):
        """Store the content to return."""
        self.content = content

    def raise_for_status(self):
        """Never raise."""


@pytest.fixture
def fake_get(monkeypatch):
    """Replace requests.get in pyghcnh.GHCNh, recording the requested URLs."""
    calls = []

    def _get(url, **kwargs):
        calls.append(url)
        return FakeResponse(b"NEW CONTENT")

    monkeypatch.setattr("pyghcnh.GHCNh.requests.get", _get)
    return calls


def _make_stale(path):
    two_months_ago = time.time() - 60 * 24 * 60 * 60
    os.utime(path, (two_months_ago, two_months_ago))


def test_update_station_list_up_to_date(ghcnh, fake_get):
    assert not ghcnh.update_station_list()
    assert fake_get == []


def test_update_station_list_stale_dry_run(ghcnh, fake_get):
    _make_stale(ghcnh.ghcnh_stationlist_path)
    assert ghcnh.update_station_list(dry_run=True)
    assert fake_get == []
    assert ghcnh.ghcnh_stationlist_path.read_text() == STATION_LIST_CSV


def test_update_station_list_stale(ghcnh, fake_get):
    _make_stale(ghcnh.ghcnh_stationlist_path)
    assert ghcnh.update_station_list()
    assert len(fake_get) == 1
    assert fake_get[0].endswith("/doc/ghcnh-station-list.csv")
    assert ghcnh.ghcnh_stationlist_path.read_bytes() == b"NEW CONTENT"


def test_update_station_list_force(ghcnh, fake_get):
    assert ghcnh.update_station_list(force=True)
    assert len(fake_get) == 1
    assert ghcnh.ghcnh_stationlist_path.read_bytes() == b"NEW CONTENT"


def test_update_station_list_missing(ghcnh, fake_get, tmp_path):
    ghcnh.ghcnh_stationlist_path = tmp_path / "subdir" / "ghcnh-station-list.csv"
    assert ghcnh.update_station_list()
    assert len(fake_get) == 1
    assert ghcnh.ghcnh_stationlist_path.read_bytes() == b"NEW CONTENT"


@pytest.mark.network
def test_get_data_network(ghcnh):
    df = ghcnh.get_data("FRI0000LFRH", start_year=2026, end_year=2026)

    assert not df.empty
    assert df.index.min() >= pd.Timestamp("2026-01-01", tz="UTC")
    assert set(df.columns) == set(GHCNh.KEPT_COLS) - {"DATE"}
    assert pd.api.types.is_numeric_dtype(df["relative_humidity"])
    assert pd.api.types.is_numeric_dtype(df["wind_direction"])

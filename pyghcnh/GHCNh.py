# For the Haversine Formula
import time
from math import asin, cos, sqrt
from pathlib import Path

import pandas as pd
import requests

from pyghcnh.constants import BASE_URL, GHCNH_STATIONLIST_FILENAME, GHCNH_STATIONLIST_PATH
from pyghcnh.degree_days import DegreeDayMethod, calculate_cdd, calculate_hdd


class GHCNh:
    """Class for the GHCNh file and methods."""

    KEPT_COLS = [
        "DATE",
        "temperature",
        "dew_point_temperature",
        "relative_humidity",
        "wet_bulb_temperature",
        "wind_direction",
        "wind_speed",
        "precipitation",
        "precipitation_3_hour",
        "precipitation_6_hour",
    ]

    def __init__(self, ghcnh_stationlist_path: Path | None = None):
        """Init the GHCNh.

        Starts by downloading the station list if it doesn't exist or is outdated, so we cache it.

        Args:
            ghcnh_stationlist_path (str): path to `ghcnh-station-list.csv`, optional,
                will default to ../support/ghcnh-station-list.csv

        """
        # If isd_history_path isn't supplied, set it to the default path
        if ghcnh_stationlist_path is None:
            self.ghcnh_stationlist_path = GHCNH_STATIONLIST_PATH
        else:
            self.ghcnh_stationlist_path = Path(ghcnh_stationlist_path)

        # See if needs updating, otherwise just link it
        self.update_station_list()
        self._parse_station_list()

    def update_station_list(self, force=False, dry_run=False):
        """Download the `ghcnh-station-list.csv` file if needed.

        It is downloaded if one of two conditions are true:
            * It does not exist
            * It is older than 1 month

        `ghcnh-station-list.csv` is the list of weather stations

        Args:
            force (bool, optional): whether to force an update even if up to date or not
            dry_run (bool, optional): only report whether an update is needed, don't download

        Returns:
            updated (bool): True if updated, False otherwise

        """
        update_needed = False

        if self.ghcnh_stationlist_path.is_file():
            tm_time = self.ghcnh_stationlist_path.lstat().st_mtime
            print(f"{self.ghcnh_stationlist_path} was last modified on: {time.ctime(tm_time)}")
            # Check if the station list is older than 1 month
            _d = 1 * 30 * 24 * 60 * 60
            if time.time() - tm_time > _d:
                update_needed = True
            elif force:
                print("Forcing update anyways")
                update_needed = True
        else:
            print(f"{self.ghcnh_stationlist_path} not found, will download it")
            update_needed = True

        if update_needed:
            if not dry_run:
                url = f"{BASE_URL}/doc/{GHCNH_STATIONLIST_FILENAME}"
                print(f"Downloading {url}")
                r = requests.get(url, allow_redirects=True, timeout=60)
                r.raise_for_status()
                self.ghcnh_stationlist_path.parent.mkdir(parents=True, exist_ok=True)
                self.ghcnh_stationlist_path.write_bytes(r.content)

        else:
            print(f"No updates necessary: {self.ghcnh_stationlist_path.name} is not older than one month")

        return update_needed

    def _parse_station_list(self):
        """Loads the station list into a pandas dataframe."""
        self.df_stations = pd.read_csv(self.ghcnh_stationlist_path, index_col=0)

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Computes the Haversine distance between two positions."""
        p = 0.017453292519943295
        a = 0.5 - cos((lat2 - lat1) * p) / 2 + cos(lat1 * p) * cos(lat2 * p) * (1 - cos((lon2 - lon1) * p)) / 2
        return 12742 * asin(sqrt(a))

    def closest_weather_stations(self, lat: float, lon: float, n: int = 5):
        """Return the closest n weather stations to a given latitude and longitude."""
        # TODO; should I mutate?
        self.df_stations["distance"] = self.df_stations.apply(
            lambda x: GHCNh.haversine_distance(lat1=x["LATITUDE"], lon1=x["LONGITUDE"], lat2=lat, lon2=lon),
            axis=1,
        )
        return self.df_stations.nsmallest(n=n, columns="distance")
        # return df_stations.index[df_stations["distance"].argmin()]

    def get_period_of_record(self, station_id: str) -> pd.DataFrame:
        """Return the period of record for a given station ID.

        Mind that this requires downloading and parsing potentially 500 MB or more of data
        """
        url = f"{BASE_URL}/access/by-station/GHCNh_{station_id}_por.psv"
        df = pd.read_csv(url, usecols=GHCNh.KEPT_COLS, sep="|")
        return GHCNh._clean_data(df)

    def get_data(self, station_id: str, start_year: int, end_year: int) -> pd.DataFrame:
        """Return the data for a given station ID and years, via Parquet files."""
        parts = []
        for y in range(start_year, end_year + 1):
            url = f"{BASE_URL}/access/by-year/{y}/parquet/GHCNh_{station_id}_{y}.parquet"
            try:
                df = pd.read_parquet(url, columns=GHCNh.KEPT_COLS)
                parts.append(df)
            except Exception as e:
                print(f"Error reading {url}: {e}")

        if not parts:
            raise ValueError(f"No data found for station {station_id} between {start_year} and {end_year}")

        df = pd.concat(parts)
        return GHCNh._clean_data(df)

    @staticmethod
    def _clean_data(df: pd.DataFrame) -> pd.DataFrame:
        """Set a UTC DatetimeIndex and convert the columns NCEI stores as strings to numeric."""
        df = df.set_index("DATE")
        df.index = pd.to_datetime(df.index, utc=True)
        for col in ("relative_humidity", "wind_direction"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        # 000 is calm per the GHCNh documentation, 999 is not a valid direction (variable/undefined)
        df.loc[df["wind_direction"] == 999, "wind_direction"] = float("nan")
        return df

    @staticmethod
    def to_daily(
        df: pd.DataFrame,
        hdd_threshold: float = 18.0,
        cdd_threshold: float = 18.0,
        method: DegreeDayMethod = DegreeDayMethod.MEAN,
        tz: str | None = None,
    ) -> pd.DataFrame:
        """Convert the hourly data to daily data, with Heating and Cooling Degree Days.

        Args:
            df (pd.DataFrame): the hourly data, as returned by get_data or get_period_of_record
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

    @staticmethod
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

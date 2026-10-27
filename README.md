# pyghcnh

[![pypi](https://img.shields.io/pypi/v/pyghcnh.svg)](https://pypi.org/project/pyghcnh/)
[![python](https://img.shields.io/pypi/pyversions/pyghcnh.svg)](https://pypi.org/project/pyghcnh/)
[![Build Status](https://github.com/jmarrec/pyghcnh/actions/workflows/dev.yml/badge.svg)](https://github.com/jmarrec/pyghcnh/actions/workflows/dev.yml)

Retrieve weather data from NOAA NCEI's
[Global Historical Climatology Network hourly (GHCNh)](https://www.ncei.noaa.gov/products/global-historical-climatology-network-hourly)
into pandas.

GHCNh replaces the Integrated Surface Database (ISD), which reached end of life in August 2025 and no longer
receives updates.

* GitHub: <https://github.com/jmarrec/pyghcnh>
* PyPI: <https://pypi.org/project/pyghcnh/>

## Installation

```bash
pip install pyghcnh
```

For development:

```bash
pip install -e ".[dev]"  # With the dev tools (pre-commit, black, isort, flake8, mypy, pytest)
pre-commit install
```

## Usage

```python
from pyghcnh.GHCNh import GHCNh

g = GHCNh()  # Downloads support/ghcnh-station-list.csv, refreshed when older than a month

# Find the closest stations to a location
g.closest_weather_stations(lat=47.75, lon=-3.37, n=5)

# Hourly data for a range of years, via the by-year Parquet files (small, fast)
df = g.get_data("FRI0000LFRH", start_year=2022, end_year=2026)

# The whole period of record, via the by-station PSV file (can be 500 MB or more)
df_por = g.get_period_of_record("FRI0000LFRH")
```

Both return a DataFrame indexed by a UTC `DatetimeIndex`, with the columns listed in `GHCNh.KEPT_COLS`.

### Daily and monthly data, with Degree Days

```python
from pyghcnh.degree_days import DegreeDayMethod
from pyghcnh.resampling import to_daily, to_monthly

# Days are split in the given time zone (UTC if omitted)
df_daily = to_daily(df, tz="Europe/Paris", hdd_threshold=18.0, cdd_threshold=18.0, method=DegreeDayMethod.MEAN)
df_monthly = to_monthly(df_daily)
```

* `to_daily` adds `temperature_min`, `temperature_max`, `hdd` and `cdd` columns. `precipitation` is summed, the other
  variables are averaged. `wind_direction` is dropped, since averaging compass directions is meaningless.
* The Degree Days use the daily temperature given by `method`:
  * `DegreeDayMethod.MEAN`: the mean of the day's observations
  * `DegreeDayMethod.METEOFRANCE`: `(Tmin + Tmax) / 2`, as Météo-France does
* `to_monthly` sums `hdd`, `cdd` and `precipitation`, takes the extremes of `temperature_min` and `temperature_max`,
  averages the rest, and adds `n_days`, the number of days with temperature data: sums are lower for a month with
  missing days.
* A day or month without any data is NaN, not 0.

The Degree Days functions also work on their own, on a float or a `pd.Series`:

```python
from pyghcnh.degree_days import calculate_cdd, calculate_hdd

calculate_hdd(12.5)  # 5.5
calculate_cdd(df_daily["temperature"], cdd_threshold=22.0)
```

## Data notes

* NCEI publishes Parquet only per year (`access/by-year/<year>/parquet/`). The period of record per station
  (`access/by-station/`) is only available as pipe-separated `.psv`.
* Station metadata (`STATION`, `Station_name`, `LATITUDE`, `LONGITUDE`, `ELEVATION`) is repeated as columns on
  every row; there is no metadata attached to the files. Station details (WMO ID, ICAO) are in the station list.
* Units: temperatures in °C, wind speed in m/s, relative humidity in %, precipitation in mm, pressure in hPa.
  See the [GHCNh documentation](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf).
* `relative_humidity` and `wind_direction` are stored as strings in the Parquet files and are converted to numeric.
  A `wind_direction` of `000` means calm; `999` is not a valid direction and is set to NaN.
* Recent observations are mostly METAR reports, every 30 minutes, with temperatures in whole °C.

## Development

```bash
pre-commit run --all-files
```

To release, bump the version (this updates `pyproject.toml` and `pyghcnh/__init__.py`, commits and tags), then push
the tag, which triggers the PyPI publishing workflow:

```bash
bump2version patch  # possible: major / minor / patch
git push --follow-tags
```

## License

MIT, see [LICENSE](LICENSE).

# pyghcnh

Retrieve weather data from NOAA NCEI's
[Global Historical Climatology Network hourly (GHCNh)](https://www.ncei.noaa.gov/products/global-historical-climatology-network-hourly)
into pandas.

GHCNh replaces the Integrated Surface Database (ISD), which reached end of life in August 2025 and no longer
receives updates.

## Installation

```bash
pip install -e .
# With the dev tools (pre-commit, black, isort, flake8, mypy)
pip install -e ".[dev]"
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

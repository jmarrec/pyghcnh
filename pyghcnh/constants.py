from pathlib import Path

# Global constants
BASE_URL = "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly"

# Where this py file is located.
ROOT_DIR = Path(__file__).resolve().parent

# Create support and weather_files directories if don't exist
SUPPORT_DIR = ROOT_DIR / "../support"
if not SUPPORT_DIR.exists():
    SUPPORT_DIR.mkdir(parents=True)

GHCNH_STATIONLIST_FILENAME = "ghcnh-station-list.csv"
GHCNH_STATIONLIST_PATH = SUPPORT_DIR / GHCNH_STATIONLIST_FILENAME

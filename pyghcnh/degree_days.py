from enum import StrEnum

import numpy as np
import pandas as pd


class DegreeDayMethod(StrEnum):
    """How the daily temperature used for the Degree Days is computed."""

    MEAN = "mean"  # Mean of the day's temperatures
    METEOFRANCE = "meteofrance"  # Mean of the day's min and max temperatures


def calculate_hdd(db_temp: float | pd.Series, hdd_threshold: float = 18.0) -> float | pd.Series:
    """Calculate the Heating Degree Days for a daily dry-bulb temperature, or a Series of them.

    A NaN temperature gives a NaN, not 0.
    """
    if isinstance(db_temp, pd.Series):
        return (hdd_threshold - db_temp).clip(lower=0.0)
    return float(np.maximum(hdd_threshold - db_temp, 0.0))


def calculate_cdd(db_temp: float | pd.Series, cdd_threshold: float = 18.0) -> float | pd.Series:
    """Calculate the Cooling Degree Days for a daily dry-bulb temperature, or a Series of them.

    A NaN temperature gives a NaN, not 0.
    """
    if isinstance(db_temp, pd.Series):
        return (db_temp - cdd_threshold).clip(lower=0.0)
    return float(np.maximum(db_temp - cdd_threshold, 0.0))

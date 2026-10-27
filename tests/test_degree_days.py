import math

import pandas as pd

from pyghcnh.degree_days import calculate_cdd, calculate_hdd


def test_calculate_hdd():
    assert calculate_hdd(10.0) == 8.0
    assert calculate_hdd(18.0) == 0.0
    assert calculate_hdd(25.0) == 0.0
    assert calculate_hdd(-2.5, hdd_threshold=15.0) == 17.5
    assert math.isnan(calculate_hdd(float("nan")))


def test_calculate_hdd_series():
    s = pd.Series([10.0, 18.0, 25.0, float("nan")])
    hdd = calculate_hdd(s)
    assert isinstance(hdd, pd.Series)
    pd.testing.assert_series_equal(hdd, pd.Series([8.0, 0.0, 0.0, float("nan")]))


def test_calculate_cdd():
    assert calculate_cdd(25.0) == 7.0
    assert calculate_cdd(18.0) == 0.0
    assert calculate_cdd(10.0) == 0.0
    assert calculate_cdd(30.0, cdd_threshold=22.0) == 8.0
    assert math.isnan(calculate_cdd(float("nan")))


def test_calculate_cdd_series():
    s = pd.Series([10.0, 18.0, 25.0, float("nan")])
    cdd = calculate_cdd(s)
    assert isinstance(cdd, pd.Series)
    pd.testing.assert_series_equal(cdd, pd.Series([0.0, 0.0, 7.0, float("nan")]))

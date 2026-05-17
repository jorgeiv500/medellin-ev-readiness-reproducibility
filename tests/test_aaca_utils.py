import pandas as pd

from scripts.aaca_utils import minmax, weighted_gini


def test_minmax_basic():
    out = minmax(pd.Series([2, 4, 6]))
    assert out.tolist() == [0.0, 0.5, 1.0]


def test_weighted_gini_equal_values():
    assert weighted_gini(pd.Series([1, 1, 1]), pd.Series([1, 2, 3])) == 0.0


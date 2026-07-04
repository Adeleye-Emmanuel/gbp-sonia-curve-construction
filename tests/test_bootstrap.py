import pytest

from src.bootstrap import bootstrap_curve, bootstrap_single_period, zero_rate_from_df


def test_bootstrap_single_period():
    D = bootstrap_single_period(0.042, 1.0)
    assert D == pytest.approx(0.9597, abs=1e-4)


def test_zero_rate_from_df():
    z = zero_rate_from_df(0.9597, 1.0)
    assert z == pytest.approx(0.0412, abs=1e-4)


def test_bootstrap_curve():
    quotes = [(1.0, 0.042), (2.0, 0.0435)]
    dfs = bootstrap_curve(quotes)
    assert dfs[1.0] == pytest.approx(0.9597, abs=1e-4)
    assert dfs[2.0] == pytest.approx(0.9183, abs=1e-4)

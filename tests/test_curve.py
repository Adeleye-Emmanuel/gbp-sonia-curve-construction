import pytest

from src.curve import Curve

PILLARS = {1.0: 0.959693, 2.0: 0.918307}


def test_discount_factor_interpolated():
    curve = Curve(PILLARS)
    assert curve.discount_factor(1.5) == pytest.approx(0.938772, abs=1e-5)


def test_discount_factor_pillar_passthrough():
    curve = Curve(PILLARS)
    assert curve.discount_factor(1.0) == 0.959693


def test_zero_rate():
    curve = Curve(PILLARS)
    assert curve.zero_rate(1.0) == pytest.approx(0.041142, abs=1e-4)


def test_forward_rate():
    curve = Curve(PILLARS)
    assert curve.forward_rate(1.0, 2.0) == pytest.approx(0.044082, abs=1e-4)


def test_discount_factor_out_of_range_raises():
    curve = Curve(PILLARS)
    with pytest.raises(ValueError):
        curve.discount_factor(0.5)
    with pytest.raises(ValueError):
        curve.discount_factor(2.5)

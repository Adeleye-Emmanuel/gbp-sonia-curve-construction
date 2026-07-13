import csv
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.bootstrap import bootstrap_curve
from src.curve import Curve
from src.scenarios import (
    apply_butterfly_shock,
    apply_historical_shock,
    apply_parametric_shock,
    apply_wing_anchored_twist,
)


REPO_ROOT = Path(__file__).resolve().parent.parent


def _build_curve_from_boe_data() -> Curve:
    quotes = []
    with open(REPO_ROOT / "data/processed/boe_ois_quotes.csv", "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            quotes.append((float(row["tenor_years"]), float(row["rate"])))
    dfs = bootstrap_curve(quotes)
    return Curve(dfs)


@pytest.fixture
def curve() -> Curve:
    return _build_curve_from_boe_data()


def test_parametric_shock_pure_parallel_shift(curve):
    shocked = apply_parametric_shock(curve, level_shift=0.005, slope_shift=0.0, pivot_tenor=5.0)

    for T, _ in curve.pillars:
        if T == 0.0:
            continue
        assert shocked.zero_rate(T) == pytest.approx(curve.zero_rate(T) + 0.005, abs=1e-9)


def test_parametric_shock_pure_twist(curve):
    shocked = apply_parametric_shock(curve, level_shift=0.0, slope_shift=0.003, pivot_tenor=5.0)

    real_pillars = [(T, D) for T, D in curve.pillars if T != 0.0]
    T_min = real_pillars[0][0]
    T_max = real_pillars[-1][0]

    assert shocked.zero_rate(5.0) == pytest.approx(curve.zero_rate(5.0), abs=1e-9)
    assert shocked.zero_rate(T_max) == pytest.approx(curve.zero_rate(T_max) + 0.003, abs=1e-9)
    assert shocked.zero_rate(T_min) == pytest.approx(curve.zero_rate(T_min) - 0.003, abs=1e-9)


def test_historical_shock_applies_observed_move(curve):
    tenors = [T for T, _ in curve.pillars]

    curve_date_a = Curve({T: math.exp(-0.040 * T) for T in tenors})
    curve_date_b = Curve({T: math.exp(-0.045 * T) for T in tenors})

    shocked = apply_historical_shock(curve, curve_date_a, curve_date_b)

    for T, _ in curve.pillars:
        if T == 0.0:
            continue
        assert shocked.zero_rate(T) == pytest.approx(curve.zero_rate(T) + 0.005, abs=1e-9)


def test_wing_anchored_twist(curve):
    wing_short, wing_long = 2.0, 10.0
    shock_short, shock_long = -0.0025, 0.0025
    shocked = apply_wing_anchored_twist(
        curve, wing_short=wing_short, wing_long=wing_long, shock_short=shock_short, shock_long=shock_long
    )

    # flat clamp below wing_short (only pillar below 2.0 is 1.0)
    assert shocked.zero_rate(1.0) == pytest.approx(curve.zero_rate(1.0) + shock_short, abs=1e-9)

    # exact anchor values at the wings themselves
    assert shocked.zero_rate(wing_short) == pytest.approx(curve.zero_rate(wing_short) + shock_short, abs=1e-9)
    assert shocked.zero_rate(wing_long) == pytest.approx(curve.zero_rate(wing_long) + shock_long, abs=1e-9)

    # linear ramp in between
    for T, _ in curve.pillars:
        if wing_short < T < wing_long:
            expected_shock = shock_short + (shock_long - shock_short) * (T - wing_short) / (wing_long - wing_short)
            assert shocked.zero_rate(T) == pytest.approx(curve.zero_rate(T) + expected_shock, abs=1e-9)


def test_butterfly_shock(curve):
    wing_short, belly, wing_long = 2.0, 5.0, 10.0
    wing_shock, belly_shock = -0.0025, 0.0025
    shocked = apply_butterfly_shock(
        curve, wing_short=wing_short, belly=belly, wing_long=wing_long, wing_shock=wing_shock, belly_shock=belly_shock
    )

    assert shocked.zero_rate(belly) == pytest.approx(curve.zero_rate(belly) + belly_shock, abs=1e-9)
    assert shocked.zero_rate(wing_short) == pytest.approx(curve.zero_rate(wing_short) + wing_shock, abs=1e-9)
    assert shocked.zero_rate(wing_long) == pytest.approx(curve.zero_rate(wing_long) + wing_shock, abs=1e-9)


def _print_zero_rate_comparison(title: str, curve: Curve, shocked: Curve) -> None:
    print(title)
    print(f"{'Tenor':>6} | {'Base z(T)':>12} | {'Shocked z(T)':>13} | {'Diff (bp)':>10}")
    print("-" * 50)
    for T, _ in curve.pillars:
        if T == 0.0:
            continue
        z_base = curve.zero_rate(T)
        z_shocked = shocked.zero_rate(T)
        print(f"{T:>6.1f} | {z_base:>12.6f} | {z_shocked:>13.6f} | {(z_shocked - z_base) * 10000:>10.4f}")
    print()


def main():
    curve = _build_curve_from_boe_data()

    parallel = apply_parametric_shock(curve, level_shift=0.005, slope_shift=0.0, pivot_tenor=5.0)
    _print_zero_rate_comparison("Parametric shock: +50bp parallel shift", curve, parallel)

    twist = apply_parametric_shock(curve, level_shift=0.0, slope_shift=0.003, pivot_tenor=5.0)
    _print_zero_rate_comparison("Parametric shock: +30bp/-30bp twist around 5Y pivot", curve, twist)

    tenors = [T for T, _ in curve.pillars]
    curve_date_a = Curve({T: math.exp(-0.040 * T) for T in tenors})
    curve_date_b = Curve({T: math.exp(-0.045 * T) for T in tenors})
    historical = apply_historical_shock(curve, curve_date_a, curve_date_b)
    _print_zero_rate_comparison(
        "Historical shock: synthetic flat 4.0% -> 4.5% move applied to BoE curve", curve, historical
    )


if __name__ == "__main__":
    main()

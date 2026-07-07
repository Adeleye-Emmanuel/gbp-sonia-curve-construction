import math

from src.curve import Curve


def apply_parametric_shock(
    curve: Curve, level_shift: float, slope_shift: float, pivot_tenor: float
) -> Curve:
    """Apply a level + piecewise-linear twist shock to a curve's zero rates.

    Twist is exactly +slope_shift at the curve's longest pillar, exactly
    -slope_shift at its shortest pillar, and exactly 0 at pivot_tenor.
    """
    T_min = curve.pillars[0][0]
    T_max = curve.pillars[-1][0]

    shocked_dfs = {}
    for T, _ in curve.pillars:
        z = curve.zero_rate(T)
        if T >= pivot_tenor:
            twist = slope_shift * (T - pivot_tenor) / (T_max - pivot_tenor)
        else:
            twist = slope_shift * (T - pivot_tenor) / (pivot_tenor - T_min)
        z_shocked = z + level_shift + twist
        shocked_dfs[T] = math.exp(-z_shocked * T)

    return Curve(shocked_dfs)


def apply_historical_shock(base_curve: Curve, curve_date_a: Curve, curve_date_b: Curve) -> Curve:
    """Apply the observed zero-rate move from curve_date_a to curve_date_b
    onto base_curve, pillar by pillar."""
    shocked_dfs = {}
    for T, _ in base_curve.pillars:
        shock = curve_date_b.zero_rate(T) - curve_date_a.zero_rate(T)
        z_shocked = base_curve.zero_rate(T) + shock
        shocked_dfs[T] = math.exp(-z_shocked * T)

    return Curve(shocked_dfs)

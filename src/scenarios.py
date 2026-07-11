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


def apply_wing_anchored_twist(
    curve: Curve, wing_short: float, wing_long: float, shock_short: float, shock_long: float
) -> Curve:
    """Apply a shock that is flat at shock_short below wing_short, flat at
    shock_long above wing_long, and linearly ramps between the two wings."""
    shocked_dfs = {}
    for T, _ in curve.pillars:
        z = curve.zero_rate(T)
        if T < wing_short:
            shock = shock_short
        elif T > wing_long:
            shock = shock_long
        else:
            shock = shock_short + (shock_long - shock_short) * (T - wing_short) / (wing_long - wing_short)
        z_shocked = z + shock
        shocked_dfs[T] = math.exp(-z_shocked * T)

    return Curve(shocked_dfs)


def apply_butterfly_shock(
    curve: Curve, wing_short: float, belly: float, wing_long: float, wing_shock: float, belly_shock: float
) -> Curve:
    """Apply a shock that is wing_shock at both wings, belly_shock at the
    belly tenor, and linearly ramps between each wing and the belly."""
    shocked_dfs = {}
    for T, _ in curve.pillars:
        z = curve.zero_rate(T)
        if T < wing_short:
            shock = wing_shock
        elif T <= belly:
            shock = wing_shock + (belly_shock - wing_shock) * (T - wing_short) / (belly - wing_short)
        elif T <= wing_long:
            shock = belly_shock + (wing_shock - belly_shock) * (T - belly) / (wing_long - belly)
        else:
            shock = wing_shock
        z_shocked = z + shock
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

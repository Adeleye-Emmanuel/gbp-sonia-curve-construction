import math


def bootstrap_single_period(par_rate: float, tenor_years: float) -> float:
    """Solve K * tau * D(T) = D(0) - D(T) for D(T), with D(0) = 1."""
    return 1.0 / (1.0 + par_rate * tenor_years)


def zero_rate_from_df(D: float, T: float) -> float:
    """Continuously compounded zero rate z = -ln(D) / T."""
    return -math.log(D) / T


def bootstrap_curve(quotes: list[tuple[float, float]]) -> dict[float, float]:
    """Bootstrap discount factors from consecutive annual par swap quotes.

    quotes: (tenor_years, par_rate) pairs, pre-sorted ascending, starting at 1.0
    with annual spacing (tau_i = 1.0 for all periods).

    D(T_n) = [1 - K_n * sum_{i=1}^{n-1} tau_i * D(T_i)] / [1 + K_n * tau_n]
    """
    discount_factors: dict[float, float] = {}
    annuity = 0.0
    for tenor, par_rate in quotes:
        D = (1.0 - par_rate * annuity) / (1.0 + par_rate * 1.0)
        discount_factors[tenor] = D
        annuity += 1.0 * D
    return discount_factors

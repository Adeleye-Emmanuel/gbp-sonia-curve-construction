"""P&L attribution combining carry/rolldown with a PCA-based curve-move
decomposition.

The observed curve move (curve_a -> curve_b) is projected onto the top
n_components principal components (level/slope/curvature, from M7's
run_pca()) to build a reconstructed shock. Whatever those components don't
explain falls out of the telescoping sum as `residual`
"""

import sys
import warnings
from datetime import date, timedelta
from math import exp
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.portfolio import Curve, Portfolio
from src.swap import Swap


def project_onto_pcs(delta_z: dict[float, float], tenors: list[float],
                      eigenvectors: np.ndarray) -> np.ndarray:
    """delta_z: real observed {tenor: change}, same tenor order as eigenvectors'
    columns. Score_i = dot product of delta_z vector with eigenvector_i
    (exact projection since eigenvectors from eigh are orthonormal)."""
    v = np.array([delta_z[T] for T in tenors])
    return v @ eigenvectors


def reconstruct_pc_shock(scores: np.ndarray, eigenvectors: np.ndarray,
                          tenors: list[float], n_components: int = 3) -> dict[float, float]:
    """delta_z_reconstructed(T) = sum_{i=1}^{n_components} scores[i] * eigenvectors[i][T]
    Using only the top 3 components is exactly where truncation (residual) comes from."""
    return {
        T: sum(scores[i] * eigenvectors[row, i] for i in range(n_components))
        for row, T in enumerate(tenors)
    }


def attribute_pnl(portfolio: Portfolio, curve_a: Curve, date_a: date,
                   curve_b: Curve, date_b: date, sonia_rate: float,
                   eigenvectors: np.ndarray, tenors: list[float],
                   n_components: int = 3) -> dict:
    days = (date_b - date_a).days
    carry = portfolio.total_carry(sonia_rate, days)
    rolldown = portfolio.total_rolldown(curve_a, date_a, sonia_rate, days)

    real_delta_z = {T: curve_b.zero_rate(T) - curve_a.zero_rate(T) for T in tenors}
    scores = project_onto_pcs(real_delta_z, tenors, eigenvectors)
    reconstructed_shock = reconstruct_pc_shock(scores, eigenvectors, tenors, n_components)

    shocked_curve = Curve({T: exp(-(curve_a.zero_rate(T) + reconstructed_shock[T]) * T) for T in tenors})

    curve_factor_pnl = portfolio.present_value(shocked_curve, date_b) - portfolio.present_value(curve_a, date_b)
    total_pnl = portfolio.present_value(curve_b, date_b) - portfolio.present_value(curve_a, date_a)
    residual = (portfolio.present_value(curve_b, date_b) - portfolio.present_value(curve_a, date_b)) - curve_factor_pnl

    # Soft check
    # the top-n_components PCs leave behind a large residual. PC1-3
    # typically explain ~99%+ of variance across the whole history, but a
    # single realized move landing partly in the untruncated PCs is a
    # genuine finding, not a bug.
    ratio = abs(residual) / abs(curve_factor_pnl)
    if ratio > 0.05:
        warnings.warn(
            f"residual is {ratio:.1%} of curve_factor_pnl (residual={residual:.2f}, "
            f"curve_factor_pnl={curve_factor_pnl:.2f}) for {date_a} -> {date_b}, "
            "above the ~5% expected given PC1-3's typical explained variance."
        )

    return {
        'carry': carry,
        'rolldown': rolldown,
        'curve_factor_pnl': curve_factor_pnl,
        'residual': residual,
        'total_pnl': total_pnl,
        'reconciled_sum': carry + rolldown + curve_factor_pnl + residual,
    }


def _curve_for_date(target_date: date) -> Curve:
    import csv
    import importlib.util

    repo_root = Path(__file__).resolve().parent.parent.parent / "project-1-curve-construction"
    spec = importlib.util.spec_from_file_location("project1_bootstrap", repo_root / "src" / "bootstrap.py")
    bootstrap_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap_module)

    historical_csv = Path(__file__).resolve().parent.parent / "data/processed/boe_historical_curves.csv"
    target_str = target_date.isoformat()
    with open(historical_csv, "r") as f:
        for row in csv.DictReader(f):
            if row["date"] == target_str:
                quotes = [(float(tenor), float(row[f"{tenor}Y"])) for tenor in range(1, 11)]
                return Curve(bootstrap_module.bootstrap_curve(quotes))
    raise ValueError(f"{target_str} not found in {historical_csv}")


def main() -> None:
    from src.curve_pca import TENORS, build_zero_rate_matrix, daily_changes, run_pca

    trade_date = date(2025, 1, 1)
    swap_a = Swap(trade_date, trade_date + timedelta(days=365 * 10), 1_000_000, 0.045, 'receiver')
    swap_b = Swap(trade_date, trade_date + timedelta(days=365 * 5), 500_000, 0.038, 'payer')
    portfolio = Portfolio([swap_a, swap_b])

    date_a, date_b = date(2025, 6, 2), date(2025, 7, 2)
    curve_a = _curve_for_date(date_a)
    curve_b = _curve_for_date(date_b)
    sonia_rate = curve_a.zero_rate(1.0)

    _, zero_rate_matrix = build_zero_rate_matrix()
    _, eigenvectors = run_pca(daily_changes(zero_rate_matrix))
    tenors = [float(tenor) for tenor in TENORS]

    result = attribute_pnl(portfolio, curve_a, date_a, curve_b, date_b, sonia_rate, eigenvectors, tenors)

    print(f"P&L attribution, {date_a} -> {date_b}:")
    for key in ('carry', 'rolldown', 'curve_factor_pnl', 'residual', 'total_pnl', 'reconciled_sum'):
        print(f"  {key:<17}{result[key]:>12,.2f}")

    result_4 = attribute_pnl(portfolio, curve_a, date_a, curve_b, date_b, sonia_rate, eigenvectors, tenors, n_components=4)
    print(f"\nWith n_components=4:")
    for key in ('carry', 'rolldown', 'curve_factor_pnl', 'residual', 'total_pnl', 'reconciled_sum'):
        print(f"  {key:<17}{result_4[key]:>12,.2f}")


if __name__ == "__main__":
    main()

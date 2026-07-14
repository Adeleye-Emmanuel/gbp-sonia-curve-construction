import csv
import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.attribution import attribute_pnl
from src.curve_pca import TENORS, build_zero_rate_matrix, daily_changes, run_pca
from src.portfolio import Portfolio
from src.swap import Curve, Swap

REPO_ROOT = Path(__file__).resolve().parent.parent.parent / "project-1-curve-construction"
HISTORICAL_CSV = Path(__file__).resolve().parent.parent / "data/processed/boe_historical_curves.csv"

_bootstrap_spec = importlib.util.spec_from_file_location("project1_bootstrap", REPO_ROOT / "src" / "bootstrap.py")
_bootstrap_module = importlib.util.module_from_spec(_bootstrap_spec)
_bootstrap_spec.loader.exec_module(_bootstrap_module)
bootstrap_curve = _bootstrap_module.bootstrap_curve

TRADE_DATE = date(2025, 1, 1)
DATE_A = date(2025, 6, 2)
DATE_B = date(2025, 7, 2)


def _curve_for_date(target_date: date) -> Curve:
    target_str = target_date.isoformat()
    with open(HISTORICAL_CSV, "r") as f:
        for row in csv.DictReader(f):
            if row["date"] == target_str:
                quotes = [(float(tenor), float(row[f"{tenor}Y"])) for tenor in range(1, 11)]
                return Curve(bootstrap_curve(quotes))
    raise ValueError(f"{target_str} not found in {HISTORICAL_CSV}")


@pytest.fixture(scope="module")
def portfolio() -> Portfolio:
    swap_a = Swap(
        trade_date=TRADE_DATE,
        maturity_date=TRADE_DATE + timedelta(days=365 * 10),
        notional=1_000_000,
        fixed_rate=0.045,
        direction='receiver',
    )
    swap_b = Swap(
        trade_date=TRADE_DATE,
        maturity_date=TRADE_DATE + timedelta(days=365 * 5),
        notional=500_000,
        fixed_rate=0.038,
        direction='payer',
    )
    return Portfolio([swap_a, swap_b])


@pytest.fixture(scope="module")
def eigenvectors():
    _, zero_rate_matrix = build_zero_rate_matrix()
    changes = daily_changes(zero_rate_matrix)
    _, eigenvectors = run_pca(changes)
    return eigenvectors


@pytest.fixture(scope="module")
def attribution_result(portfolio, eigenvectors):
    curve_a = _curve_for_date(DATE_A)
    curve_b = _curve_for_date(DATE_B)
    tenors = [float(tenor) for tenor in TENORS]
    sonia_rate = curve_a.zero_rate(1.0)

    return attribute_pnl(
        portfolio, curve_a, DATE_A, curve_b, DATE_B, sonia_rate, eigenvectors, tenors, n_components=3
    )


def test_reconciled_sum_matches_total_pnl_exactly(attribution_result):
    """The actual point of this whole project: carry + rolldown +
    curve_factor_pnl + residual is a telescoping identity, so it must equal
    total_pnl exactly -- regardless of which two dates are chosen, since
    residual is defined as whatever's left over, not computed independently."""
    assert attribution_result['reconciled_sum'] == pytest.approx(attribution_result['total_pnl'], abs=1e-6)


def test_flags_large_residual_via_warning(portfolio, eigenvectors):
    """Soft check, consistent with M7's philosophy: attribute_pnl() itself
    (not this test) flags rather than fails if the top-n_components PCs
    leave behind a large residual. PC1-3 typically explain ~99%+ of variance
    across the whole history, but this specific date pair's realized move
    lands partly outside that subspace -- a genuine finding, not a bug --
    so attribute_pnl should emit a warning for it."""
    curve_a = _curve_for_date(DATE_A)
    curve_b = _curve_for_date(DATE_B)
    tenors = [float(tenor) for tenor in TENORS]
    sonia_rate = curve_a.zero_rate(1.0)

    with pytest.warns(UserWarning, match="residual is"):
        attribute_pnl(portfolio, curve_a, DATE_A, curve_b, DATE_B, sonia_rate, eigenvectors, tenors, n_components=3)

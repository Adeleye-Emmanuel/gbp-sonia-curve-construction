import csv
import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.portfolio import Portfolio
from src.swap import Curve, Swap

REPO_ROOT = Path(__file__).resolve().parent.parent.parent / "project-1-curve-construction"

_bootstrap_spec = importlib.util.spec_from_file_location("project1_bootstrap", REPO_ROOT / "src" / "bootstrap.py")
_bootstrap_module = importlib.util.module_from_spec(_bootstrap_spec)
_bootstrap_spec.loader.exec_module(_bootstrap_module)
bootstrap_curve = _bootstrap_module.bootstrap_curve



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


TRADE_DATE = date(2025, 1, 1)


@pytest.fixture
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


def test_present_value_at_inception(portfolio, curve):
    pv = portfolio.present_value(curve, TRADE_DATE)

    assert pv == pytest.approx(18_941.81, abs=0.1)


def test_present_value_one_day_later(portfolio, curve):
    pv = portfolio.present_value(curve, TRADE_DATE + timedelta(days=1))

    assert pv == pytest.approx(19_017.08, abs=0.1)


def test_total_time_decay_matches_direct_pv_difference(portfolio, curve):
    pv_today = portfolio.present_value(curve, TRADE_DATE)
    pv_tomorrow = portfolio.present_value(curve, TRADE_DATE + timedelta(days=1))
    direct_diff = pv_tomorrow - pv_today

    aggregated = portfolio.total_time_decay(curve, TRADE_DATE, days=1)

    assert aggregated == pytest.approx(75.27, abs=0.1)
    assert direct_diff == pytest.approx(75.27, abs=0.1)

    # The actual point: aggregation (sum of each swap's own repricing) and
    # direct recomputation (portfolio PV diffed at the top level) must agree
    # exactly, not approximately — same reconciliation discipline as the
    # single-swap carry/rolldown split, one level up.
    assert aggregated == pytest.approx(direct_diff, abs=1e-9)


def test_total_dv01(portfolio, curve):
    dv01 = portfolio.total_dv01(curve, TRADE_DATE)

    assert dv01 == pytest.approx(607.97, abs=0.5)

    swap_a, swap_b = portfolio.swaps
    assert dv01 == pytest.approx(swap_a.dv01(curve, TRADE_DATE) + swap_b.dv01(curve, TRADE_DATE), abs=1e-9)
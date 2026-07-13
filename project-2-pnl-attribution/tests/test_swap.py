import csv
import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
MATURITY_DATE = TRADE_DATE + timedelta(days=365 * 10)


def test_present_value_receiver_at_inception(curve):
    swap = Swap(
        trade_date=TRADE_DATE,
        maturity_date=MATURITY_DATE,
        notional=1_000_000,
        fixed_rate=0.045,
        direction='receiver',
    )

    pv = swap.present_value(curve, as_of_date=TRADE_DATE)

    assert pv == pytest.approx(13_869.18, abs=1.0)


def test_present_value_payer_at_inception(curve):
    swap = Swap(
        trade_date=TRADE_DATE,
        maturity_date=MATURITY_DATE,
        notional=1_000_000,
        fixed_rate=0.045,
        direction='payer',
    )

    pv = swap.present_value(curve, as_of_date=TRADE_DATE)

    assert pv == pytest.approx(-13_869.18, abs=1.0)


def test_present_value_six_months_later(curve):
    swap = Swap(
        trade_date=TRADE_DATE,
        maturity_date=MATURITY_DATE,
        notional=1_000_000,
        fixed_rate=0.045,
        direction='receiver',
    )

    pv = swap.present_value(curve, as_of_date=TRADE_DATE + timedelta(days=182))

    assert pv == pytest.approx(37_872.09, abs=0.5)


def test_carry_rolldown_decomposition(curve):
    swap = Swap(
        trade_date=TRADE_DATE,
        maturity_date=MATURITY_DATE,
        notional=1_000_000,
        fixed_rate=0.045,
        direction='receiver',
    )

    # No observed overnight SONIA fixing exists in this project (only the
    # bootstrapped curve) — using the 1Y zero rate as an approximation for
    # the carry calc, per the brief.
    sonia_rate = curve.zero_rate(1.0)

    total_time_decay = swap.total_time_decay(curve, TRADE_DATE, days=1)
    carry = swap.carry(sonia_rate, days=1)
    rolldown = swap.rolldown(curve, TRADE_DATE, sonia_rate, days=1)

    assert total_time_decay == pytest.approx(130.34, abs=0.1)
    assert carry == pytest.approx(18.22, abs=0.1)
    assert rolldown == pytest.approx(112.13, abs=0.1)

    # The actual point of this design: rolldown is defined as the residual,
    # so this must reconcile exactly, by construction, not approximately.
    assert carry + rolldown == pytest.approx(total_time_decay, abs=1e-9)


def test_dv01(curve):
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

    dv01_a = swap_a.dv01(curve, TRADE_DATE)
    dv01_b = swap_b.dv01(curve, TRADE_DATE)

    assert dv01_a == pytest.approx(837.79, abs=0.5)
    assert dv01_b == pytest.approx(-229.82, abs=0.5)
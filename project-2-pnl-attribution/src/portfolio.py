import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.swap import Curve, Swap


class Portfolio:
    def __init__(self, swaps: list[Swap] = None):
        self.swaps = swaps if swaps is not None else []

    def add_swap(self, swap: Swap) -> None:
        self.swaps.append(swap)

    def present_value(self, curve: Curve, as_of_date: date) -> float:
        return sum(s.present_value(curve, as_of_date) for s in self.swaps)

    def total_carry(self, sonia_rate: float, days: int = 1) -> float:
        return sum(s.carry(sonia_rate, days) for s in self.swaps)

    def total_rolldown(self, curve: Curve, as_of_date: date, sonia_rate: float, days: int = 1) -> float:
        return sum(s.rolldown(curve, as_of_date, sonia_rate, days) for s in self.swaps)

    def total_time_decay(self, curve: Curve, as_of_date: date, days: int = 1) -> float:
        return sum(s.total_time_decay(curve, as_of_date, days) for s in self.swaps)

    def total_dv01(self, curve: Curve, as_of_date: date) -> float:
        return sum(s.dv01(curve, as_of_date) for s in self.swaps)


def _build_curve_from_boe_data() -> Curve:
    import csv
    import importlib.util

    repo_root = Path(__file__).resolve().parent.parent.parent / "project-1-curve-construction"
    spec = importlib.util.spec_from_file_location("project1_bootstrap", repo_root / "src" / "bootstrap.py")
    bootstrap_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap_module)

    quotes = []
    with open(repo_root / "data/processed/boe_ois_quotes.csv") as f:
        for row in csv.DictReader(f):
            quotes.append((float(row["tenor_years"]), float(row["rate"])))

    return Curve(bootstrap_module.bootstrap_curve(quotes))


def main() -> None:
    curve = _build_curve_from_boe_data()

    trade_date = date(2025, 1, 1)
    swap_a = Swap(trade_date, trade_date + timedelta(days=365 * 10), 1_000_000, 0.045, 'receiver')
    swap_b = Swap(trade_date, trade_date + timedelta(days=365 * 5), 500_000, 0.038, 'payer')
    portfolio = Portfolio([swap_a, swap_b])

    pv_today = portfolio.present_value(curve, trade_date)
    pv_tomorrow = portfolio.present_value(curve, trade_date + timedelta(days=1))
    sonia_rate = curve.zero_rate(1.0)

    print(f"Portfolio PV today:    {pv_today:>12,.2f}")
    print(f"Portfolio PV tomorrow: {pv_tomorrow:>12,.2f}")
    print(f"Direct PV diff:        {pv_tomorrow - pv_today:>12,.2f}")
    print(f"total_time_decay:      {portfolio.total_time_decay(curve, trade_date, days=1):>12,.2f}")
    print(f"total_carry:           {portfolio.total_carry(sonia_rate, days=1):>12,.2f}")
    print(f"total_rolldown:        {portfolio.total_rolldown(curve, trade_date, sonia_rate, days=1):>12,.2f}")
    print(f"total_dv01:            {portfolio.total_dv01(curve, trade_date):>12,.2f}")

if __name__ == "__main__":
    main()

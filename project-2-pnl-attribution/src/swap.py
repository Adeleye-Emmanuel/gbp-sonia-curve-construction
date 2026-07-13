import importlib.util
from datetime import date, timedelta
from pathlib import Path
import sys

_CURVE_PATH = Path(__file__).resolve().parent.parent.parent / "project-1-curve-construction" / "src" / "curve.py"
_spec = importlib.util.spec_from_file_location("project1_curve", _CURVE_PATH)
_curve_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_curve_module)
Curve = _curve_module.Curve

_SCENARIOS_PATH = Path(__file__).resolve().parent.parent.parent / "project-1-curve-construction" / "src" / "scenarios.py"
_scenarios_spec = importlib.util.spec_from_file_location("project1_scenarios", _SCENARIOS_PATH)
_scenarios_module = importlib.util.module_from_spec(_scenarios_spec)
sys.modules["src.curve"] = _curve_module
_scenarios_spec.loader.exec_module(_scenarios_module)
apply_parametric_shock = _scenarios_module.apply_parametric_shock


class Swap:
    def __init__(self, trade_date: date, maturity_date: date, notional: float,
                 fixed_rate: float, direction: str):
        self.trade_date = trade_date
        self.maturity_date = maturity_date
        self.notional = notional
        self.fixed_rate = fixed_rate
        self.direction = direction

        coupon_dates = []
        current = maturity_date
        while current > trade_date:
            coupon_dates.append(current)
            current -= timedelta(days=365)
        coupon_dates.reverse()
        self.coupon_schedule = coupon_dates

        accrual_fractions = []
        period_start = trade_date
        for coupon_date in coupon_dates:
            accrual_fractions.append(self.remaining_tenor(period_start, coupon_date))
            period_start = coupon_date
        self.accrual_fractions = accrual_fractions

    def remaining_tenor(self, as_of_date: date, target_date: date) -> float:
        return (target_date - as_of_date).days / 365.0

    def present_value(self, curve: Curve, as_of_date: date) -> float:
        pv_fixed = self.notional * self.fixed_rate * sum(
            tau * curve.discount_factor(self.remaining_tenor(as_of_date, coupon_date))
            for tau, coupon_date in zip(self.accrual_fractions, self.coupon_schedule)
            if coupon_date > as_of_date
        )

        T_n = self.remaining_tenor(as_of_date, self.maturity_date)
        pv_floating = self.notional * (1 - curve.discount_factor(T_n))

        pv_receiver = pv_fixed - pv_floating
        return pv_receiver if self.direction == 'receiver' else -pv_receiver

    def carry(self, sonia_rate: float, days: int = 1) -> float:
        """Pure coupon-economics carry: (K - sonia_rate) * tau * notional.
        sonia_rate must be supplied by the caller — this project has no
        observed overnight SONIA fixing, only the bootstrapped curve, so
        there is no single 'correct' internal source for it."""
        tau = days / 365.0
        return self.notional * (self.fixed_rate - sonia_rate) * tau

    def total_time_decay(self, curve: Curve, as_of_date: date, days: int = 1) -> float:
        """Full repricing difference: PV(as_of+days) - PV(as_of), same curve.
        Exact by construction — no approximation, captures everything."""
        return (self.present_value(curve, as_of_date + timedelta(days=days))
                - self.present_value(curve, as_of_date))

    def rolldown(self, curve: Curve, as_of_date: date, sonia_rate: float, days: int = 1) -> float:
        """Defined as the residual: total_time_decay - carry.
        NOT computed independently — guaranteed to reconcile by construction."""
        return self.total_time_decay(curve, as_of_date, days) - self.carry(sonia_rate, days)
    
    def dv01(self, curve: Curve, as_of_date: date) -> float:
        """Dollar value of a 1bp parallel shift in the curve.
        Computed by bumping the curve and re-pricing the swap."""
        shocked_curve = apply_parametric_shock(curve, level_shift = 0.0001, slope_shift = 0.0, pivot_tenor = 5.0)
        return self.present_value(curve, as_of_date) - self.present_value(shocked_curve, as_of_date)
"""Cross-check our hand-rolled bootstrap against QuantLib-Python.

Builds a SONIA OIS curve in QuantLib from the same quotes used by our own
bootstrap_curve(), and compares discount factors at each of the 10 annual
pillars (1Y-10Y). This is a sanity check on our own implementation, not a
replacement for it -- differences are reported honestly, not corrected away.

Bootstrap choice: ql.PiecewiseLogCubicDiscount, the standard/default choice
for OIS discount curves in QuantLib (smooth, well-behaved instantaneous
forwards; used in the QuantLib cookbook examples for OIS/Libor curves).

Two QuantLib curves are built:
  1. Using ql.Sonia(), which carries its own UK fixing calendar and
     ModifiedFollowing business-day adjustment -- pillar dates get shifted
     off the naive calendar date our own bootstrap assumes (a known,
     documented v1 simplification -- see CLAUDE.md).
  2. Using a custom OvernightIndex built on ql.NullCalendar() with
     Unadjusted conventions throughout, so QuantLib's pillar dates land on
     exactly the same naive calendar dates (valuation_date + n years) that
     our own bootstrap implicitly assumes. This isolates how much of any
     discrepancy in (1) is just the calendar/business-day effect, versus
     the curve-construction/interpolation itself.

We also dump the exact conventions QuantLib used to build each OISRateHelper
(day count, payment frequency, settlement/fixing days, calendar) to diff
directly against our own assumptions, and rebuild curve (1) with
ql.PiecewiseLogLinearDiscount instead of ql.PiecewiseLogCubicDiscount to test
whether interpolation choice (rather than conventions) explains the
UK-calendar discrepancy -- if pillar DFs are identical between log-linear and
log-cubic, that rules out interpolation as the cause.

All comparisons are reported side by side; no correction is applied.
"""

import csv

import QuantLib as ql

from src.bootstrap import bootstrap_curve

QUOTES_CSV = "data/processed/boe_ois_quotes.csv"


def load_quotes(csv_path: str = QUOTES_CSV) -> list[tuple[float, float]]:
    quotes = []
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            quotes.append((float(row["tenor_years"]), float(row["rate"])))
    return quotes


def build_uk_helpers(quotes: list[tuple[float, float]]) -> list[ql.OISRateHelper]:
    """OISRateHelpers using ql.Sonia()'s own UK calendar + ModifiedFollowing."""
    sonia = ql.Sonia()
    return [
        ql.OISRateHelper(
            0,
            ql.Period(int(tenor), ql.Years),
            ql.QuoteHandle(ql.SimpleQuote(rate)),
            sonia,
        )
        for tenor, rate in quotes
    ]


def build_null_helpers(quotes: list[tuple[float, float]]) -> list[ql.OISRateHelper]:
    """OISRateHelpers using a NullCalendar index + Unadjusted conventions,
    so pillar dates land on the same naive calendar dates our own bootstrap
    implicitly assumes."""
    null_calendar = ql.NullCalendar()
    flat_sonia = ql.OvernightIndex(
        "SONIA-flat", 0, ql.GBPCurrency(), null_calendar, ql.Actual365Fixed()
    )
    return [
        ql.OISRateHelper(
            0,
            ql.Period(int(tenor), ql.Years),
            ql.QuoteHandle(ql.SimpleQuote(rate)),
            flat_sonia,
            paymentCalendar=null_calendar,
            fixedCalendar=null_calendar,
            overnightCalendar=null_calendar,
            paymentConvention=ql.Unadjusted,
            convention=ql.Unadjusted,
        )
        for tenor, rate in quotes
    ]


_BDC_NAMES = {0: "Following", 1: "ModifiedFollowing", 4: "Unadjusted"}
_FREQ_NAMES = {1: "Annual"}
_AVERAGING_NAMES = {0: "Simple", 1: "Compound"}


def print_conventions(helpers: list[ql.OISRateHelper], label: str) -> None:
    """Introspect the actual conventions QuantLib used to build the OIS swaps
    underlying each rate helper, so they can be diffed directly against our
    own bootstrap's assumptions (annual, Act/365, no settlement/fixing lag).
    """
    print(f"Conventions used to construct each OISRateHelper ({label}):")
    swaps = [h.swap() for h in helpers]

    day_counts = {str(s.fixedDayCount()) for s in swaps}
    freqs = {s.paymentFrequency() for s in swaps}
    conventions = {s.paymentConvention() for s in swaps}
    fixing_days = {s.overnightIndex().fixingDays() for s in swaps}
    fixing_cals = {str(s.overnightIndex().fixingCalendar()) for s in swaps}
    averaging = {s.averagingMethod() for s in swaps}
    lockout = {s.lockoutDays() for s in swaps}

    print(f"  fixed/floating day count : {', '.join(day_counts)}")
    print(f"  payment frequency        : {', '.join(_FREQ_NAMES.get(f, str(f)) for f in freqs)}")
    print(f"  payment/date convention  : {', '.join(_BDC_NAMES.get(c, str(c)) for c in conventions)}")
    print(f"  settlement/fixing days   : {', '.join(str(d) for d in fixing_days)}")
    print(f"  fixing calendar          : {', '.join(fixing_cals)}")
    print(f"  averaging method         : {', '.join(_AVERAGING_NAMES.get(a, str(a)) for a in averaging)}")
    print(f"  lockout days             : {', '.join(str(d) for d in lockout)}")
    print("  (our own bootstrap: Act/365, annual, no settlement/fixing lag, no calendar)")
    print()


def print_comparison_table(
    title: str,
    quotes: list[tuple[float, float]],
    left_label: str,
    left_values: dict[float, float],
    right_label: str,
    right_values: dict[float, float],
) -> None:
    print(title)
    print(f"{'Tenor':>6} | {left_label:>14} | {right_label:>14} | {'Diff (bp)':>10}")
    print("-" * 56)
    for tenor, _ in quotes:
        left = left_values[tenor]
        right = right_values[tenor]
        diff_bp = (left - right) * 10000
        print(f"{tenor:>6.1f} | {left:>14.6f} | {right:>14.6f} | {diff_bp:>10.4f}")
    print()


def main():
    quotes = load_quotes()
    our_dfs = bootstrap_curve(quotes)

    valuation_date = ql.Date(30, 6, 2026)

    uk_helpers_1 = build_uk_helpers(quotes)
    print_conventions(uk_helpers_1, "UK calendar, production build")

    ql.Settings.instance().evaluationDate = valuation_date
    uk_cubic_curve = ql.PiecewiseLogCubicDiscount(valuation_date, uk_helpers_1, ql.Actual365Fixed())
    uk_cubic_curve.enableExtrapolation()
    uk_calendar = ql.UnitedKingdom()
    uk_maturity_dates = {
        tenor: uk_calendar.advance(valuation_date, ql.Period(int(tenor), ql.Years), ql.ModifiedFollowing)
        for tenor, _ in quotes
    }
    uk_cubic_dfs = {tenor: uk_cubic_curve.discount(uk_maturity_dates[tenor]) for tenor, _ in quotes}
    print_comparison_table(
        "(1) QuantLib (UK calendar + ModifiedFollowing, LogCubic) vs ours:",
        quotes,
        "Our D(T)",
        our_dfs,
        "QuantLib D(T)",
        uk_cubic_dfs,
    )

    null_helpers = build_null_helpers(quotes)
    print_conventions(null_helpers, "NullCalendar, naive-date build")

    ql.Settings.instance().evaluationDate = valuation_date
    null_cubic_curve = ql.PiecewiseLogCubicDiscount(valuation_date, null_helpers, ql.Actual365Fixed())
    null_cubic_curve.enableExtrapolation()
    null_calendar = ql.NullCalendar()
    null_maturity_dates = {
        tenor: null_calendar.advance(valuation_date, ql.Period(int(tenor), ql.Years), ql.Unadjusted)
        for tenor, _ in quotes
    }
    null_cubic_dfs = {tenor: null_cubic_curve.discount(null_maturity_dates[tenor]) for tenor, _ in quotes}
    print_comparison_table(
        "(2) QuantLib (NullCalendar + Unadjusted, naive dates, LogCubic) vs ours:",
        quotes,
        "Our D(T)",
        our_dfs,
        "QuantLib D(T)",
        null_cubic_dfs,
    )

    uk_helpers_2 = build_uk_helpers(quotes)
    ql.Settings.instance().evaluationDate = valuation_date
    uk_linear_curve = ql.PiecewiseLogLinearDiscount(valuation_date, uk_helpers_2, ql.Actual365Fixed())
    uk_linear_curve.enableExtrapolation()
    uk_linear_dfs = {tenor: uk_linear_curve.discount(uk_maturity_dates[tenor]) for tenor, _ in quotes}
    print_comparison_table(
        "(3) QuantLib LogLinear vs LogCubic (UK calendar, everything else identical):",
        quotes,
        "LogLinear D(T)",
        uk_linear_dfs,
        "LogCubic D(T)",
        uk_cubic_dfs,
    )


if __name__ == "__main__":
    main()

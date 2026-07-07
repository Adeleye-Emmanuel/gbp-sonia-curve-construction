# GBP SONIA Curve Construction & Scenario Engine

A from-scratch implementation of a GBP SONIA OIS discount curve — bootstrapped, interpolated, independently validated against QuantLib, and stress-tested via a scenario engine. Part 1 of a 3-project rates/cross-asset quant strat portfolio (curve construction → P&L attribution → trading signals).

## Why this exists

Building a curve from a library call (`ql.PiecewiseLogCubicDiscount(...)`) proves you can use a tool. Deriving the bootstrap equation, implementing it, and then validating it against that same library proves you understand *why* the tool produces the numbers it does. This project deliberately does the former from scratch and uses the latter only as a cross-check.

## Methodology

### Single-curve framework

SONIA is an overnight, near risk-free rate. Unlike the old LIBOR world — which needed two curves (one to discount cash flows via OIS, one to project the credit-risky LIBOR floating leg) — a SONIA OIS swap uses **the same curve to discount and to project the floating leg**. This project builds one curve, not two, and that simplification is the direct consequence of the post-LIBOR RFR transition, not an arbitrary shortcut.

### Bootstrapping — the par-swap equation

A SONIA OIS curve isn't observed directly; it's inferred sequentially from par swap rates across a tenor ladder. For a swap with annual fixed coupons:

```
Fixed leg PV  = N · K · Σ τᵢ · D(Tᵢ)
Floating leg PV = N · [D(T₀) − D(Tₙ)]     (telescoping: compounded daily SONIA
                                            discounted on its own curve collapses
                                            to a ratio of start/end discount factors)
```

Setting the two equal (par swap, zero NPV at inception) and rearranging for the one new unknown at each tenor:

```
D(Tₙ) = [1 − Kₙ · Σᵢ₌₁ⁿ⁻¹ τᵢ·D(Tᵢ)] / [1 + Kₙ·τₙ]
```

Each new pillar only introduces one new unknown, because every earlier discount factor is already known — that's the entire bootstrap, implemented in `src/bootstrap.py` as a running-sum (O(n)) loop rather than recomputing the sum from scratch each time.

Continuously-compounded zero rates are derived from discount factors via `z(T) = -ln(D(T))/T`, and forward rates via `f(T1,T2) = -ln(D(T2)/D(T1))/(T2-T1)` — both implemented in `src/curve.py` so that every rate quantity is *derived from* the discount factor, never interpolated independently (see below for why that matters).

### Interpolation — log-linear on discount factors

Three candidate methods were compared (linear-on-zero-rate, linear-on-discount-factor, log-linear-on-discount-factor) and produced meaningfully different values for the *same* two input pillars — there is no single "correct" answer for points between quoted tenors, only a modeling choice. Log-linear-on-discount-factor was selected because linear interpolation on zero rates produces a well-known artifact: a discontinuous jump in the *instantaneous forward rate* at every pillar boundary (an illustrative test case showed a jump from 7.5% to 4.7% at a single point), which is economically implausible. Log-linear-on-DF avoids this.

Design rule enforced in `Curve`: `discount_factor(T)` is the single source of truth. `zero_rate()` and `forward_rate()` both call it internally rather than re-interpolating independently — this guarantees the object represents one internally consistent curve rather than several disagreeing ones.

## Data

Source: [Bank of England daily/monthly OIS (SONIA) yield curve archive](https://www.bankofengland.co.uk/statistics/yield-curves) — a free, publicly available Anderson–Sleath fitted nominal spot curve, published out to 25Y.

**Known approximation, stated explicitly**: these are BoE's *fitted* spot rates, not raw broker-screen par swap quotes. They are used here as par-rate-equivalent inputs to the bootstrap. This is a deliberate simplification for a free-data-only project, not a claim that these are literally tradeable swap quotes.

## Worked example (real data)

Ten quotes pulled from the BoE archive (most recent available date at time of writing):

| Tenor | Par rate (BoE-derived) | Bootstrapped D(T) | Zero rate z(T) |
|---|---|---|---|
| 1Y  | 3.910% | 0.962375 | 3.835% |
| 2Y  | 3.984% | 0.924822 | 3.908% |
| 3Y  | 3.986% | 0.889333 | 3.909% |
| 4Y  | 3.996% | 0.854890 | 3.920% |
| 5Y  | 4.028% | 0.820675 | 3.953% |
| 6Y  | 4.076% | 0.786470 | 4.003% |
| 7Y  | 4.134% | 0.752333 | 4.065% |
| 8Y  | 4.197% | 0.718407 | 4.134% |
| 9Y  | 4.262% | 0.684847 | 4.206% |
| 10Y | 4.328% | 0.651801 | 4.280% |

Sanity checks passed: discount factors strictly decreasing and bounded in (0,1); zero rates in a plausible ~3.8%–4.3% band, rising gently with maturity, consistent with a mildly upward-sloping curve.

## Validation against QuantLib

The same 10 quotes were independently bootstrapped in QuantLib (`ql.OISRateHelper` + `ql.PiecewiseLogCubicDiscount`) and compared pillar-by-pillar:

| Tenor | Diff (bp) |
|---|---|
| 1Y, 3Y | ~0.0 |
| 2Y | +0.97 |
| 4Y | −0.90 |
| 5Y | +0.87 |
| 6Y–8Y | +1.6 to +1.7 |
| 9Y | +0.79 |
| 10Y | +2.25 |

**Residual explained, not dismissed**: two hypotheses were tested and ruled out — the interpolation method (log-linear vs log-cubic only affects values *between* pillars, never *at* them, by construction of what interpolation means) and QuantLib's UK business-day calendar (removing it via `ql.NullCalendar()` did not close the gap). The conventions dump confirmed identical day count (Act/365), frequency (annual), and settlement lag (0) on both sides — same convention *names*. The leading candidate, not yet directly isolated, is that this project's naive `τ=1.0` per annual period differs from QuantLib's actual calendar-date Act/365 fraction whenever a period spans a leap day (`τ≈1.0027`), which would explain both the small magnitude and the non-monotonic, alternating sign pattern across tenors (see Known Limitations).

## Scenario engine

Two shock types, both implemented in zero-rate space and both returning a new, independent `Curve`:

**Parametric shock** (`apply_parametric_shock`) — a level shift plus a piecewise-linear twist pivoted at a chosen tenor:
```
twist(T) =  slope_shift · (T − pivot)/(T_max − pivot),   T ≥ pivot
            slope_shift · (T − pivot)/(pivot − T_min),   T <  pivot
z_shocked(T) = z(T) + level_shift + twist(T)
```
This reproduces textbook parallel shift (`slope_shift=0`), steepener/flattener (`level_shift=0`), and any combination (bull/bear steepening/flattening), verified against hand-derived expected values at the pivot and both endpoints.

**Historical shock** (`apply_historical_shock`) — applies an *observed* move between two real curves onto a third base curve, with no pivot parameter, since the shape of a real historical move is whatever the market actually did:
```
shock(T) = z_dateB(T) − z_dateA(T)
z_shocked(T) = z_base(T) + shock(T)
```

Worked example — +30bp/−30bp twist around the 5Y pivot, applied to the real BoE-derived curve above:

| Tenor | Base z(T) | Shocked z(T) | Diff (bp) |
|---|---|---|---|
| 1Y | 3.835% | 3.535% | −30.00 |
| 2Y | 3.908% | 3.683% | −22.50 |
| 5Y | 3.953% | 3.953% | 0.00 |
| 10Y | 4.280% | 4.580% | +30.00 |

Note the asymmetric slope either side of the pivot (steeper ramp 1Y→5Y than 5Y→10Y) — a direct consequence of the pivot sitting closer to the short end than the long end, not a bug.

## Known limitations (v1 scope, deliberate)

- **Annual pillars only, 1Y–10Y, no gaps.** Avoids the interpolation-during-bootstrap complexity that arises when market tenors skip years (e.g. a 15Y/20Y/25Y quote requires interpolating unquoted intermediate years *before* the bootstrap equation for that tenor can even be set up).
- **Naive calendar-date day counts, no business-day/holiday adjustment.** Real swaps adjust maturity dates that fall on weekends/UK bank holidays (Modified Following); this project uses unadjusted calendar dates. Believed to be the primary driver of the small QuantLib residual above, specifically via leap-year `τ` deviation from exactly 1.0 — not yet directly isolated with a dedicated test.
- **`apply_historical_shock` validated only on synthetic data.** Meaningful use requires multiple real historical dates from BoE's *daily* archive (only a single date from the *monthly* archive has been pulled so far) — a data-ingestion follow-up, not a code gap.

## Repo structure

```
src/            bootstrap.py, curve.py, scenarios.py
validation/     quantlib_check.py
tests/          mirrors src/
data/raw/       downloaded BoE archive
data/processed/ derived (tenor, rate) quotes
```

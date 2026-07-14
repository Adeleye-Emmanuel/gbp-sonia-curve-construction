# Rates Portfolio P&L Attribution Engine

Values a portfolio of GBP SONIA swaps and decomposes its P&L into carry, rolldown, curve-move (via PCA), and residual — each component reconciling exactly to the portfolio's real, fully-repriced total. Project 2 of a 3-project rates/cross-asset quant strat portfolio, built directly on Project 1's `Curve`.

## Why this exists

A number like "the portfolio made £6,242 this month" is not useful on its own. The question a desk actually asks is *why* — how much was earned just by holding the position (carry/rolldown), how much came from the market actually moving, and how much is left unexplained. This project answers that with full repricing throughout, not linear approximations, so every attribution is exact by construction rather than approximately correct.

## Methodology

### Swap valuation

A swap is valued from its two legs, using the same par-swap logic and floating-leg telescoping identity as Project 1's bootstrap:

```
PV_fixed    = notional · fixed_rate · Σ τᵢ · D(Tᵢ)
PV_floating = notional · [1 − D(Tₙ)]
PV_receiver = PV_fixed − PV_floating,   PV_payer = −PV_receiver
```

`Tᵢ`/`Tₙ` are computed fresh from whatever valuation date is asked for — a `Swap` holds only immutable trade facts (dates, notional, rate, direction) plus a cached coupon schedule (fixed for its lifetime, since it depends only on trade/maturity dates). It never stores a curve; one is always passed in fresh, so there is no possibility of a swap referencing a stale market state.

### Carry and rolldown

Carry has an independent, closed-form definition — it doesn't need the curve's shape at all:

```
Carry = notional · (fixed_rate − sonia_rate) · τ
```

Rolldown does **not** have an independent formula of its own — it's inherently comparative (value at one remaining maturity vs. a shorter one, same curve), so it's defined as the residual of the exact, fully-repriced total:

```
Total_time_decay = PV(curve, date+1) − PV(curve, date)     [same curve, exact by full repricing]
Rolldown := Total_time_decay − Carry
```

This guarantees `Carry + Rolldown = Total_time_decay` by construction — not something separately verified to hold, but something that cannot fail to hold given how rolldown is defined.

### Risk — DV01 and key-rate duration

Both computed by bump-and-reprice rather than a closed-form duration formula, since portfolio value here is a function of an entire curve (via interpolation and bootstrapping), not a single closed-form yield:

- **DV01**: shock every pillar by +1bp in parallel, reprice, difference against base.
- **Key-rate duration**: shock a *single* pillar's zero rate, leave every other real pillar untouched, rebuild the curve. The resulting shock is a self-generating "tent" — zero at neighboring pillars, full size at the bumped one — purely as a byproduct of the log-linear interpolation already built into `Curve`, with no separate tent formula required. Summing all key-rate durations reconciles to the parallel DV01 exactly.

### PCA on historical curve moves

Built on **daily zero-rate changes**, not levels — rate levels are non-stationary (a multi-year drift would dominate a level-based covariance matrix and produce a PC1 that mostly just recovers time itself, not a genuine co-movement pattern). Each historical BoE quote is bootstrapped into a real zero-rate curve first (consistent with Project 1's par-rate treatment of BoE data), then differenced day-over-day, then covariance-eigendecomposed.

### Full P&L attribution

The observed move between two real curves is projected onto the top-N principal components to get factor scores, which are used to reconstruct an approximate shock — that shock is then **fully repriced**, not scaled from a small-shock sensitivity. This avoids introducing any linear/convexity approximation error into the decomposition; the only source of residual is deliberate PC truncation (components beyond N not included), not numerical approximation:

```
Total P&L      = PV(curve_B, date_B) − PV(curve_A, date_A)
Curve-move P&L = PV(curve_B, date_B) − PV(curve_A, date_B)      [total minus time-decay, exact]
Curve-factor   = PV(curve_A shocked by PC reconstruction, date_B) − PV(curve_A, date_B)
Residual      := Curve-move P&L − Curve-factor P&L
```

`Carry + Rolldown + Curve-factor P&L + Residual = Total P&L` holds exactly, always, by the same telescoping-sum logic as the rolldown definition above.

## Worked example (real data, 2025-06-02 → 2025-07-02)

Portfolio: 10Y receiver (£1,000,000 @ 4.50%) + 5Y payer (£500,000 @ 3.80%).

| Component | Value (n_components=3) | Value (n_components=4) |
|---|---|---|
| Carry | £509.97 | £509.97 |
| Rolldown | £1,794.00 | £1,794.00 |
| Curve-factor P&L | £4,455.95 | £3,900.48 |
| Residual | −£517.44 | +£38.02 |
| **Total P&L** | **£6,242.47** | **£6,242.47** |
| **Reconciled sum** | **£6,242.47** | **£6,242.47** |

Both reconcile exactly to the same total, as required — moving explanatory power from "residual" to "curve-factor" as more components are added is expected, not a sign anything changed underneath.

**Investigating the residual — a real finding, not an assumption.** Key-rate duration shows this portfolio carries a sharply negative sensitivity concentrated at the 5Y point (−£194.45), driven entirely by the 5Y payer, while every other tenor is positive. The first three principal components (level, slope, curvature) capture only the curve's broadest global shapes; they have no mechanism to represent a real move that happens to wiggle specifically around one pillar. A portfolio with concentrated single-tenor risk is exactly the case where PC1–3 truncation shows up larger than typical — and it does: adding a 4th component drops the residual roughly 13x (−£517.44 → +£38.02), direct evidence for the explanation rather than a plausible-sounding story left unverified.

**Decomposing the curve-factor P&L itself by individual factor** (n=3, same date pair): level alone would produce +£7,296.66 — nearly 64% larger than the actual combined figure — with slope clawing back −£3,216.74 (44% of the level move) and curvature adding a modest +£376.03. A level-only estimate would have overstated the curve-driven P&L by roughly £2,840 for this specific portfolio.

**Is the residual typical, or was this date pair unlucky?** Sampling ~15 one-month windows across the historical archive: 5 of 15 (33%) exceed a 5% residual-to-curve-factor ratio. The median ratio is a reassuring 1.14%, but the distribution has a fat right tail — mean 13.37%, pulled up by two real outliers (one where residual actually *exceeded* curve-factor P&L in magnitude). The June→July example sits on the low end of the breaching windows, not the worst case. Conclusion: a >5% residual isn't rare for this portfolio — it happens roughly 1 month in 3 — so `curve_factor_pnl` at a fixed component count should be read as a useful approximation, not trusted blindly window over window.

**Does key-rate duration correctly predict scenario direction?** Tested against all 10 of Project 1's scenario shocks. 7 scenarios (parallel shifts and all level+twist combinations) move every pillar in the same direction, so KRD sign alone predicts them — 0 contradictions. The remaining 3 (2s10s steepener/flattener, butterfly) move tenors in opposite directions by construction, so KRD sign can't call them and they were deliberately left unpredicted. Notably: 2s10s steepener lost money while 2s10s flattener gained, tracking the 10Y point's dominant KRD (over 3x every other tenor combined) rather than the 5Y point's negative KRD — a naive "short the 5Y" read would have guessed the wrong driver for these two scenarios specifically.

## Known limitations

- **No observed SONIA fixing**: `sonia_rate` for carry calculations is approximated as `curve.zero_rate(1.0)` — a full year's average rate, not a true overnight fixing. This project has no source for the latter.
- **PC truncation is a modeling choice, not an error term**: `curve_factor_pnl`/`residual` depend on how many principal components are used — see the worked example above for how material this choice can be for a portfolio with concentrated single-tenor risk.
- **Curve extended to T=0**: Project 1's `Curve` was extended with the trivial `D(0)=1` anchor, enabling valuation of swaps inside their final year. This implies a flat zero rate below the shortest quoted pillar (1Y) — a mathematically clean extension, not new market data.
- **Naive dates, no business-day convention**: inherited from Project 1 — still deferred, documented there.

## Repo structure

```
src/            swap.py, portfolio.py, curve_pca.py, attribution.py
tests/          mirrors src/
notebooks/      01_pnl_attribution.ipynb — full walkthrough with the findings above
data/processed/ boe_historical_curves.csv
```
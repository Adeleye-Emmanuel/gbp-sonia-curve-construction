# GBP SONIA Curve Construction — Project Context

## What this is
A rates quant strat portfolio project: bootstrap a GBP SONIA OIS discount curve from
market-consistent par swap rates, build a scenario engine on top of it. Part 1 of a
3-project portfolio (curve construction → P&L attribution → trading signals).

## Core methodology decisions (do not silently change these)
- **Single-curve framework**: SONIA is (near) risk-free and overnight, so one curve both
  discounts cash flows AND projects the floating leg. No separate projection curve.
- **Par swap equation** used for bootstrapping:
  `K · Σ(τᵢ · D(Tᵢ)) = D(0) − D(Tₙ)` — the floating leg telescopes to D(0) − D(Tₙ), it is
  NOT built from individual daily SONIA fixings.
- **Zero rate convention**: continuous compounding, `z = -ln(D(T)) / T`.
- **v1 scope (deliberate simplifications, documented in README, not silently absorbed)**:
  - Annual pillars only, 1Y through 10Y, no gaps — avoids interpolation-during-bootstrap
    complexity for now.
  - Naive calendar-date day-count fractions (Act/365), NO business day adjustment /
    UK holiday calendar yet. This is a known, intentional v1 limitation — do not
    "fix" this unprompted; it's a planned M10 refinement.
  - Day count: Act/365 (standard GBP convention).
  - For later versions we can test the below assumption:
  Known residual: ~1-2bp discrepancy vs QuantLib cross-check likely due to naive tau=1.0 vs actual Act/365 day-count fractions (leap years cause tau≈1.0027 for periods spanning 29 Feb). Confirmed candidate, not yet isolated with a direct
  tau comparison.

## Data
- Source: Bank of England published OIS (SONIA) yield curve archive — free, daily,
  fitted curve out to 25Y maturity. Used to derive par-rate-like quotes at standard
  tenors (treat as if they were market swap quotes).
- Cross-validation: bootstrap the same quotes independently in QuantLib and diff
  against this project's own discount factors — used as a sanity check, not a
  replacement for the hand-rolled bootstrap.

## Working method (important — do not skip)
This is a learning project, not a "just make it work" task. For any new *conceptual*
piece (e.g. new formula, new financial concept, a design choice with real tradeoffs),
implement exactly what's specified in the brief I give you — do not silently add
extra sophistication, alternate conventions, or "improvements" beyond what's asked.
If you think something in a brief is wrong or could be better, flag it and ask,
don't just change it.

For plumbing/mechanical work (data ingestion scripts, test scaffolding, repo
structure) — normal engineering judgment is fine.

## Repo structure
src/ — bootstrap.py, curve.py, interpolation.py, instruments.py
validation/ — quantlib_check.py
tests/ — mirrors src/
data/raw/, data/processed/
notebooks/ — exploratory only, not production logic

## Conventions
- Python 3.12, pytest for tests
- Every new function gets a test that encodes a hand-derived expected value where
  one exists (not just "does it run") — tolerance typically 1e-4
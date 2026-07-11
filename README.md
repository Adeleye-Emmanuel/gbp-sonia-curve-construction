# Rates Quant Strat Portfolio

A multi-project portfolio exploring the rates trading stack end to end: building a
market-consistent discount curve from scratch, attributing a rates portfolio's P&L
back to the curve moves that drove it, and eventually generating trading signals
from historical rate behaviour. Each project builds on the outputs of the one
before it.

- [`project-1-curve-construction/`](project-1-curve-construction/) — bootstraps a
  GBP SONIA OIS discount curve from BoE-published market data, with log-linear
  interpolation, a QuantLib cross-check, and a scenario/shock engine for stress
  testing the curve. Complete (v1).
- [`project-2-pnl-attribution/`](project-2-pnl-attribution/) — attributes a rates
  portfolio's P&L to carry/rolldown, curve-move decomposition, and residual, built
  on top of Project 1's `Curve` object. In progress.

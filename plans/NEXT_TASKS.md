# Next Tasks

Tasks are ordered by engineering risk. Do not skip validation to work on optional features.

## P0 — Keep main green and harden failure behavior

1. Keep Ruff, strict MyPy, Pytest, Bandit, migration round-trip and Docker green on every `main` change.
2. Add focused database-connectivity failure tests around durable execution and recovery.
3. Add provider/replay interruption and duplicate/reordered-event cases beyond existing normalization coverage.
4. Verify operational-health mode changes remain fail-safe when persisted/restored.
5. Keep `docs/IMPLEMENTATION_STATUS.md` synchronized with actual CI evidence.

## P1 — Backtest analytics

The minimal event-driven backtester is validated. Next:

1. Record an explicit equity curve at deterministic event/trade boundaries.
2. Calculate total/net return and maximum drawdown from the equity curve.
3. Add deterministic trade statistics: count, winning/losing closed trades, gross profit/loss and payoff/profit-factor where denominators are valid.
4. Keep fees/slippage explicit and separate from strategy alpha.
5. Add regression fixtures proving repeated runs return identical analytics.
6. Do not add Sharpe/Sortino until return-period semantics are explicit.

## P2 — Deterministic SMC / regime expansion

Already validated: trend/BOS/CHoCH, ATR-ratio volatility regime, deterministic FVG lifecycle.

Next:

1. Define MSS separately from CHoCH with explicit event-time confirmation and availability semantics.
2. Add selected liquidity concepts only where objective rules can be encoded and regression-tested.
3. Add additional indicators such as ADX only with trusted reference/regression tests.
4. Version feature/strategy outputs before adding a scanner.

## P3 — External read-only historical data

Already validated: provider-neutral historical source contract + local JSONL implementation.

Next:

1. Verify current official Upstox historical market-data API behavior, authentication, limits and timestamp semantics.
2. Verify current official Dhan historical market-data API behavior, authentication, limits and timestamp semantics.
3. Implement provider adapters only against verified official behavior.
4. Preserve provider/exchange/ingestion timestamps and explicit recorded/live labels.
5. Retry only idempotent read operations using bounded policies.
6. Persist raw/provider evidence separately from normalized events where practical.

## P4 — Trading safety before any real order path

Already validated: kill switches, READ_ONLY/CLOSE_ONLY/HALTED modes, persisted/recovered controls, health gating, transaction rollback and reconciliation/restart recovery.

Next:

1. Broaden injected database/network/provider failure tests.
2. Add broker interfaces in read-only/shadow-safe mode only after historical adapters are verified.
3. Define all live-trading gates as an explicit policy before any order-submission adapter is implemented.
4. Do not add real order submission until explicit user approval exists.

## Later

- walk-forward/OOS/Monte Carlo
- options engine
- portfolio construction/optimization expansion
- frontend workspaces
- ML subsystem
- controlled live release

## Constraints

- Work directly on `main`; do not create branches/PRs unless the user changes that instruction.
- Live execution remains disabled.
- No hardcoded success responses representing real integrations.
- No secrets in the repository.
- No broad placeholder package generation.
- A capability remains unverified until its required checks actually pass.
- Recorded/mock/fixture data must be clearly labeled and never represented as live market data.
# Next Tasks

Tasks are ordered by engineering risk. Do not skip validation to work on optional features.

## P0 — Keep main green and expand failure evidence

1. Keep Ruff, strict MyPy, Pytest, Bandit, migration round-trip and Docker green on every `main` change.
2. Add focused failure tests for database unavailability/transaction failure and confirm no partial economic state is published.
3. Add duplicate/reordered replay-event failure cases beyond existing normalization tests.
4. Keep `docs/IMPLEMENTATION_STATUS.md` synchronized with actual CI evidence.

## P1 — Minimal event-driven backtester

1. Reuse `ReplayStream`, `ReplayStrategyPipeline`, strategy/decision/risk contracts and paper execution semantics.
2. Define explicit backtest execution assumptions: market fill price, spread/slippage hooks, fees/costs and rejected orders.
3. Produce deterministic trade/equity/P&L results from recorded events.
4. Prove no future candle/event is visible to a decision.
5. Add deterministic repeated-run regression tests.
6. Keep backtest and live/paper strategy interfaces aligned rather than creating a separate strategy implementation.

## P2 — Deterministic regime and SMC expansion

1. Add simple deterministic regime primitives from tested trend state plus volatility inputs.
2. Define MSS separately from CHoCH with explicit confirmation/availability semantics before implementation.
3. Add selected liquidity concepts only where objective rules can be encoded and regression-tested.
4. Add additional indicators such as ADX only with trusted reference/regression tests.
5. Version feature/strategy outputs before adding a scanner.

## P3 — Provider-neutral external historical data

1. Define a read-only historical-data adapter protocol around canonical instruments/events/candles.
2. Verify current official Upstox/Dhan historical APIs before implementing provider adapters.
3. Preserve provider/exchange/ingestion timestamps and explicit recorded/live labels.
4. Add rate-limit/retry policy only for idempotent read operations.
5. Persist raw/provider evidence separately from normalized events where practical.

## P4 — Trading safety before any real order path

Already validated: global/account/strategy/instrument kill switches, READ_ONLY/CLOSE_ONLY/HALTED modes and persisted/recovered risk-control state.

Next:

1. Broaden injected restart/database/network failure tests.
2. Add operational-health gating that can move the platform into READ_ONLY/CLOSE_ONLY/HALTED deterministically.
3. Add broker interfaces in read-only/shadow-safe mode only after historical adapters are verified.
4. Do not add real order submission until explicit live-trading gates and user approval exist.

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
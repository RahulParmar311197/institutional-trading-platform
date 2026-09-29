# Next Tasks

Tasks are ordered by engineering risk. Do not skip validation to work on optional features.

## P0 — Get `main` green

1. Resolve all Ruff failures.
2. Resolve all MyPy failures without weakening strict typing.
3. Resolve all Pytest failures without weakening valid tests.
4. Resolve Bandit findings by root cause.
5. Confirm Docker image builds in CI.
6. Add migration apply/rollback integration validation against PostgreSQL.
7. Add structured logging/request correlation that is actually exercised.
8. Keep `docs/IMPLEMENTATION_STATUS.md` synchronized with CI evidence.

## P1 — Complete first paper-trading vertical slice

1. Add explicit decision contract between strategy and risk.
2. Persist order intents, OMS orders, order events and fills.
3. Add deterministic paper realized/unrealized P&L.
4. Add reconciliation between internal OMS/fills/positions and paper-broker truth.
5. Add journal/audit records for signal → risk → order → fill → position.
6. Add E2E test proving one paper trade through the full path.
7. Add restart/idempotency tests for duplicate fills and recovered open orders.

## P2 — Quant expansion after vertical slice is green

1. Complete multi-timeframe candle aggregation/session boundaries.
2. Add ATR/ADX/VWAP and regression/reference tests.
3. Add deterministic swing/market-structure primitives.
4. Add BOS/CHoCH/FVG only with explicit no-look-ahead definitions and tests.
5. Add regime engine and scanner only after feature primitives are stable.

## Later

- event-driven backtester/replay
- Upstox/Dhan adapters in safe/shadow mode
- options engine
- frontend workspaces
- ML subsystem
- controlled live release

## Constraints

- Work directly on `main`; do not create branches/PRs for this project unless the user changes that instruction.
- Live execution remains disabled.
- No hardcoded success responses representing real integrations.
- No secrets in the repository.
- No broad placeholder package generation.
- A capability remains unverified until its required checks actually pass.
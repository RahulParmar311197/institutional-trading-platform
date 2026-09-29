# Next Tasks

Tasks are ordered by engineering risk. Do not skip validation to work on optional features.

## P0 — Keep infrastructure evidence complete

1. Add a real Redis integration test for readiness/connectivity.
2. Keep Ruff, strict MyPy, Pytest, Bandit, migration round-trip and Docker green on every `main` change.
3. Add focused failure tests for DB/Redis unavailability and transaction rollback where not already covered.
4. Keep `docs/IMPLEMENTATION_STATUS.md` synchronized with actual CI evidence.

## P1 — Provider-neutral market data and replay

1. Define canonical recorded market-event envelopes with source/exchange/provider/ingestion timestamps and sequence metadata.
2. Add historical/recorded event ingestion from local fixtures/Parquet-compatible boundaries without pretending it is live data.
3. Add normalization and duplicate/out-of-order handling before candle generation.
4. Implement a deterministic replay clock/event stream with pause/step/speed-independent event ordering.
5. Feed replayed events through the existing data-quality → candle/features → strategy/decision/risk → durable paper path.
6. Add E2E replay test proving identical deterministic results across repeated runs.

## P2 — Deterministic quant/SMC expansion

1. Define explicit trend-state rules from confirmed swings/structure breaks.
2. Add CHoCH/MSS semantics only after availability timing is specified and tested.
3. Add FVG lifecycle: open, partial mitigation, filled and invalidated using only information available at each timestamp.
4. Add additional indicators such as ADX only with trusted reference/regression tests.
5. Add regime primitives after structure semantics stabilize.
6. Add scanner only after feature outputs are versioned/stable.

## P3 — Trading safety before external brokers

1. Add global/account/strategy/instrument kill-switch primitives.
2. Add close-only/read-only/halted operational modes.
3. Persist/recover active risk locks.
4. Expand failure injection: DB loss, Redis loss, duplicate/out-of-order events, transaction failure and restart.
5. Only then begin Upstox/Dhan adapters in read-only/shadow-safe mode.

## Later

- event-driven backtester built on replay interfaces
- advanced validation/walk-forward/Monte Carlo
- options engine
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
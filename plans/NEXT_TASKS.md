# Next Tasks

Tasks are ordered by engineering risk. Do not skip validation to work on optional features.

## P0 — Keep main green and harden failure behavior

1. Keep Ruff, strict MyPy, Pytest, Bandit, migration round-trip, Docker build and runtime import smoke green on every `main` change.
2. Expand replay/provider interruption cases with deterministic restart/resume semantics where required.
3. Add more persistence/network fault injection around recovery and control-state transitions.
4. Keep `docs/IMPLEMENTATION_STATUS.md` synchronized with actual cumulative CI evidence.

Already validated in this area: audit-transaction rollback, duplicate-fill rollback, database-unavailable fail-closed behavior, bounded transient provider retries, persistent risk controls, operational health gating and persisted health escalation.

## P1 — Safe external historical service

Already validated: local JSONL historical source, provider OHLC model/normalization, mock-contract Upstox/Dhan read-only clients, transient-only retry policy, and dated provider-ID resolution.

Next:

1. Add a service that resolves a canonical instrument to a provider ID for the requested historical interval.
2. Reject or explicitly split requests that cross provider-identifier validity boundaries; never guess which ID applies.
3. Keep provider raw bars distinct from normalized closed candles and preserve provenance.
4. Add optional authenticated read-only smoke tests only when credentials/entitlements are securely supplied at runtime.
5. Do not treat mocked HTTP contract tests as real provider validation.

## P2 — Research robustness

Already validated: event-driven backtester, explicit fees/slippage, risk rejection, no-look-ahead regression, event-time equity curve and core metrics.

Next:

1. Define period semantics before adding Sharpe/Sortino or annualization.
2. Add explicit dataset boundaries before walk-forward/OOS tooling.
3. Add deterministic checkpoint/resume behavior if long replay/backtest runs require continuation.
4. Add walk-forward/OOS only after leakage protections remain green.

## P3 — Deterministic SMC / strategy evolution

Already validated: BOS/CHoCH, ATR-ratio regime, FVG lifecycle and displacement-confirmed MSS.

Next:

1. Add selected liquidity concepts only where objective event-time rules can be encoded and regression-tested.
2. Add feature/strategy output versioning before scanner work.
3. Add additional indicators only with trusted reference/regression tests.
4. Keep strategy logic shared across replay/backtest/paper paths.

## P4 — Trading safety before any real order path

Already validated: kill switches, READ_ONLY/CLOSE_ONLY/HALTED modes, persisted/recovered controls, persisted health escalation, reconciliation/recovery and a deny-by-default live-gate policy.

Next:

1. Integrate every live-gate input into any future execution boundary before an order API is introduced.
2. Add broker interfaces in read-only/shadow-safe mode only when useful and verified.
3. Do not add real order submission until all safety gates are implemented, validated and explicitly approved by the user.

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
- Mock/recorded/fixture data must be clearly labeled and never represented as live provider data.

# Next Tasks

Tasks are ordered by engineering risk. Do not skip validation to work on optional features.

## P0 — Keep main green and harden failure behavior

1. Keep Ruff, strict MyPy, Pytest, Bandit, migration round-trip, Docker build and runtime import smoke green on every `main` change.
2. Extend checkpoint/resume into orchestration-level persistence only where long replay/backtest jobs require durable continuation.
3. Add more persistence/network/provider fault injection around recovery and control-state transitions.
4. Keep `docs/IMPLEMENTATION_STATUS.md` synchronized with actual cumulative CI evidence.

Already validated: audit rollback, duplicate-fill rollback, database-unavailable fail-closed behavior, transient provider retries, duplicate-provider-bar rejection, persistent controls/health escalation, replay checkpoint integrity, and Dhan provider-master conflict safety.

## P1 — Safe external historical/provider evidence

Already validated: local JSONL historical source, provider OHLC model/normalization, mock-contract Upstox/Dhan clients, point/range provider reference resolution, canonical Upstox historical service, canonical Dhan daily cash/derivative services, migration `0006` provider classification metadata, and Dhan compact-master parser/synchronizer. The synchronizer updates only existing security-ID links, pre-validates conflicts and does not auto-create canonical instruments.

Next:

1. Add a secure read-only Dhan provider-master retrieval boundary with explicit URL allowlisting, timeout and maximum response size; feed bytes/text only into the tested parser/synchronizer.
2. Keep live-master retrieval distinct from fixture-tested parsing; do not claim freshness unless a real retrieval succeeds and is validated.
3. Add optional authenticated historical-provider smoke tests only when credentials/entitlements are securely supplied at runtime.
4. Consider canonical Dhan intraday orchestration only after provider-local datetime/session semantics and request splitting are explicit.
5. Keep provider raw evidence distinct from normalized candles and preserve provenance.
6. Do not treat mocked HTTP/service tests as real provider validation.

## P2 — Research robustness

Already validated: event-driven backtester, explicit fees/slippage, risk rejection, no-look-ahead regression, event-time equity curve/core metrics, and versioned JSON replay checkpoint/resume bound to normalized event content.

Next:

1. Define period semantics before Sharpe/Sortino or annualization.
2. Add explicit dataset boundaries before walk-forward/OOS tooling.
3. Add durable checkpoint storage/job orchestration only if long-running workflows require cross-process restart.
4. Add walk-forward/OOS only after leakage protections remain green.

## P3 — Deterministic SMC / strategy evolution

Already validated: BOS/CHoCH, ATR-ratio regime, FVG lifecycle, displacement-confirmed MSS, and parameter-specific EMA crossover `v1` strategy identity.

Next:

1. Add selected liquidity concepts only where objective event-time rules can be regression-tested.
2. Add broader feature-output versioning and strategy registry/lifecycle semantics before scanner work.
3. Add indicators only with trusted reference/regression tests.
4. Keep strategy logic shared across replay/backtest/paper paths.

## P4 — Trading safety before any real order path

Already validated: kill switches, READ_ONLY/CLOSE_ONLY/HALTED modes, persisted/recovered controls, health escalation, reconciliation/recovery and a deny-by-default live-gate policy.

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
- A capability remains unverified until its required checks pass.
- Mock/recorded/fixture data must be clearly labeled and never represented as live provider data.

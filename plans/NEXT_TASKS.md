# Next Tasks

Tasks are ordered by engineering risk. Do not skip validation to work on optional features.

## P0 — Keep main green and harden failure behavior

1. Keep Ruff, strict MyPy, Pytest, Bandit, migration round-trip, Docker build and runtime import smoke green on every `main` change.
2. Add more persistence/network/provider fault injection around recovery and control-state transitions, but first make initialization-vs-corruption semantics explicit where missing persisted state is currently valid first-run behavior.
3. Keep `docs/IMPLEMENTATION_STATUS.md` synchronized with actual cumulative CI evidence.

Already validated: audit rollback, duplicate-fill rollback, database-unavailable fail-closed behavior, transient provider retries, duplicate-provider-bar rejection, persistent controls/health escalation, stream-bound replay checkpoint integrity, atomic replay checkpoint files, full-state backtest checkpoint/resume, schema-valid checkpoint economic/pipeline consistency validation, atomic in-memory restore failure, interrupted checkpoint replacement preserving the last good file, Dhan master conflict safety, bounded master retrieval and transactional refresh.

## P1 — Safe external historical/provider evidence

Already validated: local JSONL historical source, provider OHLC model/normalization, mock-contract Upstox/Dhan clients, point/range provider reference resolution, canonical Upstox historical service, canonical Dhan daily cash/derivative services, migration `0006` provider classification metadata, Dhan compact-master parser/synchronizer, exact-URL bounded retrieval, and fetch→parse→transactional-sync orchestration. Synchronization updates only existing security-ID links, pre-validates conflicts and never auto-creates canonical instruments.

Next:

1. Validate a real Dhan compact-master transfer in an environment that supports the provider's octet-stream response; record source URL, retrieval time/hash or equivalent freshness evidence without auto-linking instruments.
2. Keep real-transfer validation distinct from MockTransport-tested retrieval code; do not claim freshness or provider availability until a real transfer succeeds.
3. Add optional authenticated historical-provider smoke tests only when credentials/entitlements are securely supplied at runtime.
4. Consider canonical Dhan intraday orchestration only after provider-local datetime/session semantics and request splitting are explicit.
5. Keep provider raw evidence distinct from normalized candles and preserve provenance.
6. Do not treat mocked HTTP/service tests as real provider validation.

## P2 — Research robustness

Already validated: event-driven backtester, explicit fees/slippage, risk rejection, no-look-ahead regression, event-time equity curve/core metrics, atomic replay checkpoint storage, full-state deterministic backtest checkpoint/resume, internal economic/pipeline consistency validation, atomic failed-restore behavior and interrupted local checkpoint replacement preservation. A fresh backtester restored after an executed simulated fill produces the exact uninterrupted result; changed stream/configuration fails closed.

Next:

1. Define period semantics before Sharpe/Sortino or annualization.
2. Add explicit dataset boundaries before walk-forward/OOS tooling.
3. Add a scheduler/distributed research job layer only when an actual workflow requires it; do not infer distributed exactly-once semantics from local checkpointing.
4. Add walk-forward/OOS only after leakage protections remain green.

## P3 — Deterministic SMC / strategy evolution

Already validated: BOS/CHoCH, ATR-ratio regime, FVG lifecycle, displacement-confirmed MSS, parameter-specific EMA crossover `v1` identity, an immutable strategy registry with ACTIVE/RETIRED lifecycle plus historical retired-version resolution, and versioned parameter-specific regime feature outputs carrying instrument/event-time provenance.

Next:

1. Extend versioned feature-output contracts to the next derived feature only when its reproducibility boundary is explicit; avoid premature generic framework abstraction.
2. Add selected liquidity concepts only where objective event-time rules can be regression-tested.
3. Add additional strategies/indicators only with trusted reference/regression tests and immutable version identity.
4. Keep strategy logic shared across replay/backtest/paper paths.

## P4 — Trading safety before any real order path

Already validated: kill switches, READ_ONLY/CLOSE_ONLY/HALTED modes, persisted/recovered controls, health escalation, reconciliation/recovery and a deny-by-default live-gate policy.

Next:

1. Integrate every live-gate input into any future execution boundary before an order API is introduced.
2. Add broker interfaces in read-only/shadow-safe mode only when useful and verified.
3. Do not add real order submission until all safety gates are implemented, validated and explicitly approved by the user.

## Later

- walk-forward/OOS/Monte Carlo
- distributed research orchestration when justified by workload
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

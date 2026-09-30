# Next Tasks

Tasks are ordered by engineering risk. Do not skip validation to work on optional features.

## P0 — Keep main green and harden failure behavior

1. Keep Ruff, strict MyPy, Pytest, Bandit, migration round-trip, Docker build and runtime import smoke green on every `main` change.
2. Continue persistence/network/provider failure injection only where a distinct fail-closed invariant remains missing; persisted-control missing state, malformed mode/scope/key encodings and database-unavailable load/mutation paths are already covered.
3. Keep `docs/IMPLEMENTATION_STATUS.md` synchronized with actual cumulative CI evidence.

Already validated: audit rollback, duplicate-fill rollback, database-unavailable durable execution and control recovery, transient provider retries, duplicate-provider-bar rejection, persisted controls/health escalation, migration-backed operational-state initialization, missing/corrupt control-state rejection, replay/backtest checkpoint integrity/atomicity, interrupted checkpoint replacement preservation, Dhan master conflict safety, bounded master retrieval and transactional refresh.

## P1 — Safe external historical/provider evidence

Already validated: local JSONL historical source, provider OHLC model/normalization, mock-contract Upstox/Dhan clients, point/range provider reference resolution, canonical Upstox historical service, canonical Dhan daily cash/derivative services, migration `0006` provider classification metadata, Dhan compact-master parser/synchronizer, exact-URL bounded retrieval, and fetch→parse→transactional-sync orchestration. Synchronization updates only existing security-ID links, pre-validates conflicts and never auto-creates canonical instruments.

Next:

1. Validate a real Dhan compact-master transfer in an environment that supports the provider's octet-stream response; record source URL, retrieval time/hash or equivalent freshness evidence without auto-linking instruments.
2. Keep real-transfer validation distinct from MockTransport-tested retrieval code; do not claim freshness or provider availability until a real transfer succeeds.
3. Add optional authenticated historical-provider smoke tests only when credentials/entitlements are securely supplied at runtime.
4. Consider canonical Dhan intraday orchestration only after provider-local datetime/session semantics and request splitting are explicit.
5. Keep provider raw evidence distinct from normalized candles and preserve provenance.

## P2 — Research robustness

Already validated: event-driven backtesting, explicit fees/slippage/risk rejection/no-look-ahead behavior, full-state checkpoint/recovery, versioned dataset boundaries, explicit regular return periods, deterministic rolling walk-forward folds with optional embargo and deterministic fold IDs, versioned OOS provenance/result identities, explicit Sharpe/Sortino conventions, fixed-strategy cold-start test-fold evaluation that rejects train/out-of-window event leakage, and fold-level aggregate reporting with strict provenance compatibility/order checks. Aggregate reports deliberately do not sum or compound potentially overlapping test folds.

Next:

1. Define warm-up/fitted-state provenance before allowing any training-window-derived state into OOS evaluation. The current evaluator is intentionally cold-start/test-only.
2. Define a separate selection/validation contract before optimizer/parameter search; a test fold must never choose or influence the configuration evaluated on itself.
3. Keep training/test data isolation explicit across any future warm-start or selection workflow.
4. Add Monte Carlo only after sampling unit, replacement policy, path count/seed and preserved dependencies are explicit.
5. Add distributed research orchestration only when an actual workload requires it; local checkpointing does not imply distributed exactly-once semantics.

## P3 — Deterministic SMC / strategy evolution

Already validated: BOS/CHoCH, ATR-ratio regime, FVG lifecycle, displacement-confirmed MSS, parameter-specific EMA crossover `v1` identity, immutable strategy registry lifecycle, and versioned parameter-specific regime feature outputs carrying instrument/event-time provenance.

Next:

1. Extend versioned feature-output contracts only when the next derived feature has an explicit event-time/reproducibility boundary; avoid premature generic framework abstraction.
2. Add selected liquidity concepts only where objective event-time rules can be regression-tested.
3. Add additional strategies/indicators only with trusted reference/regression tests and immutable version identity.
4. Keep strategy logic shared across replay/backtest/paper paths.

## P4 — Trading safety before any real order path

Already validated: kill switches, READ_ONLY/CLOSE_ONLY/HALTED modes, migration-backed persisted/recovered controls, health escalation, reconciliation/recovery and a deny-by-default live-gate policy.

Next:

1. Integrate every live-gate input into any future execution boundary before an order API is introduced.
2. Add broker interfaces in read-only/shadow-safe mode only when useful and verified.
3. Do not add real order submission until all safety gates are implemented, validated and explicitly approved by the user.

## Later

- walk-forward optimization/parameter search after leakage-safe warm-up/selection contracts
- Monte Carlo
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

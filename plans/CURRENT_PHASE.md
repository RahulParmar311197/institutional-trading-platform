# Current Phase

## Phase 5 — Event-driven research, external read-only data and failure hardening

Status: `IN_PROGRESS`

### Validated milestone

The deterministic paper/replay/research vertical slice is green on `main`:

Recorded events / local JSONL / provider historical bars → normalization → closed candles → versioned strategy identity → TradingDecision → independent risk → OMS/paper execution → position/P&L → audit/reconciliation/recovery.

Canonical read-only historical slices remain validated for Upstox and Dhan cash/derivative daily data. Dhan derivative routing requires explicit persisted provider metadata; identifier rollovers and classification mismatches fail before HTTP.

The Dhan compact instrument-master boundary is validated in CI with mocked HTTP plus real PostgreSQL: exact official URL → bounded streaming retrieval → strict CSV parsing → conflict-safe synchronization → transactional commit. Synchronization enriches only pre-existing Dhan security-ID links.

Research restartability has two validated layers: replay cursor/stream identity can be persisted locally using bounded atomic fsynced files, and backtests checkpoint the full deterministic economic/pipeline state. Schema-valid checkpoints are cross-checked against replay-prefix, trade/P&L/position/fee/drawdown invariants; failed restore is atomic; injected replace failure preserves the last committed checkpoint.

Strategy identity is explicit and immutable through the registry lifecycle. The regime engine is the first concrete derived feature with a parameter-specific versioned identity plus instrument/event-time provenance.

Research reproducibility now has explicit temporal, provenance and metric contracts:

- train/validation/test windows are timezone-aware, half-open and non-overlapping with UTC-canonical deterministic identity;
- periodic returns require an explicitly declared regular interval; annualization is never inferred;
- deterministic rolling walk-forward folds use explicit train/test lengths, step and optional embargo, emit only full folds and carry deterministic UTC-canonical fold IDs;
- OOS provenance binds the exact boundary, fold/spec, strategy ID, ordered feature IDs, normalized stream digest, backtest configuration digest and execution assumptions;
- OOS result identity covers the complete deterministic backtest result plus provenance;
- Sharpe uses arithmetic mean excess return over sample standard deviation; Sortino uses arithmetic mean above target over population lower-partial-moment downside deviation; both require explicit `periods_per_year` and return `None` on a zero denominator.

### Safety controls already validated

- live trading disabled by default
- deny-by-default live-trading policy; no real order adapter
- global/account/strategy/instrument kill switches
- READ_ONLY/CLOSE_ONLY/HALTED operational modes
- persistence/recovery of risk controls and health-driven restrictions
- transactional rollback/no in-memory economic publication on duplicate fill, audit failure or unavailable database
- bounded transient-only historical provider retries; auth/client failures are not retried
- duplicate historical timestamps fail closed
- invalid Dhan expiry codes/classifications fail before HTTP
- provider-master redirects, oversized responses, invalid encoding/schema and metadata conflicts fail closed
- replay/backtest checkpoint stream/config mismatch, malformed schema and internally inconsistent economic/pipeline state fail closed
- failed backtest restore leaves the existing in-memory session unchanged
- interrupted local checkpoint replacement preserves the previously committed checkpoint
- research dataset partitions reject overlap and naive timestamps
- return calculations and risk-adjusted metrics reject irregular/noncontiguous periods
- walk-forward folds keep training before test data and support explicit embargo separation
- runtime container import smoke after production-only dependency install

### Quant/research foundation already validated

- canonical instrument master/provider identifiers and migration `0006` provider classification metadata
- point-in-time/full-range provider reference resolution with missing/overlap/rollover rejection
- read-only Upstox/Dhan HTTP contract clients using mocked transports
- canonical Upstox and Dhan daily services using PostgreSQL identifier resolution plus mocked HTTP
- Dhan compact-master parser, bounded fetcher, conflict-safe synchronizer and transactional refresh
- provider OHLC/provenance/duplicate-timestamp validation and OHLC→closed-candle normalization
- deterministic replay plus atomic local replay checkpoint persistence
- full-state deterministic backtest checkpoint/resume with cross-field/prefix integrity checks
- configurable sessions, session-aligned multi-timeframe candles, SMA/EMA/RSI/ATR/VWAP
- confirmed swings, BOS/CHoCH, FVG lifecycle, displacement-confirmed MSS and deterministic trend/volatility regime
- versioned EMA crossover identity plus immutable strategy registry/lifecycle
- versioned parameter-specific regime feature outputs with event-time provenance
- versioned train/validation/test research boundaries with UTC-canonical identity
- explicit regular return-period semantics without implicit annualization
- deterministic rolling walk-forward fold construction with optional embargo and deterministic fold identity
- versioned OOS provenance/result identity binding data, strategy, feature and execution assumptions
- explicitly defined Sharpe/Sortino conventions with mandatory annualization metadata
- event-driven backtester with fees/slippage, risk rejection, no-look-ahead regression, equity curve and core metrics

### Current objective

Deepen failure hardening and move from reproducibility primitives into leakage-safe walk-forward evaluation while preserving canonical mapping and trading-safety boundaries. Validate real provider evidence only where the environment and credentials actually permit it.

Immediate work:

1. Add more persistence/network/provider fault injection around recovery and control-state transitions, but first make first-run initialization versus persisted-state corruption semantics explicit where absence is currently valid.
2. Add walk-forward strategy evaluation that consumes the tested fold and OOS provenance contracts without parameter selection or optimizer shortcuts.
3. Extend versioned feature-output contracts to the next derived feature only when its event-time/reproducibility boundary is explicit.
4. Validate an actual Dhan compact-master transfer in an environment that supports the provider's octet-stream response; record freshness/evidence without auto-linking instruments.
5. Add optional authenticated historical-provider smoke validation only when credentials/entitlements are explicitly and securely supplied; never commit credentials.

### Engineering gates

Every addition must keep `main` green across Ruff, strict MyPy, PostgreSQL migrations when applicable, the full unit/integration suite, Bandit, migration rollback/reapply, Docker build and runtime smoke.

### Explicitly out of scope for the current phase

- unrestricted live order placement
- any real broker order submission
- broker credentials in source control
- distributed research orchestration before a real workload justifies it
- optimizer-driven parameter selection before leakage-safe evaluation contracts exist
- ML-controlled execution
- profitability claims
- Kubernetes/microservice expansion

### Safety invariant

Live trading remains disabled. No external adapter or future execution path may bypass data quality, canonical instrument mapping, decision, independent risk, OMS, audit, reconciliation, persisted controls, operational health or the explicit live gate.

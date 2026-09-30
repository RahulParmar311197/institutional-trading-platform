# Current Phase

## Phase 5 — Event-driven research, external read-only data and failure hardening

Status: `IN_PROGRESS`

### Validated milestone

The deterministic paper/replay/research vertical slice is green on `main`:

Recorded events / local JSONL / provider historical bars → normalization → closed candles → versioned strategy identity → TradingDecision → independent risk → OMS/paper execution → position/P&L → audit/reconciliation/recovery.

Canonical read-only historical slices remain validated for Upstox and Dhan cash/derivative daily data. Dhan derivative routing requires explicit persisted provider metadata; identifier rollovers and classification mismatches fail before HTTP.

The Dhan compact instrument-master boundary is validated in CI with mocked HTTP plus real PostgreSQL: exact official URL → bounded streaming retrieval → strict CSV parsing → conflict-safe synchronization → transactional commit. Synchronization enriches only pre-existing Dhan security-ID links.

Research restartability now has two validated layers:

- replay cursor/stream identity can be persisted locally using bounded, atomic, fsynced checkpoint files;
- backtests can checkpoint the full deterministic state: replay cursor, closed/open candle state, simulated position/P&L, trades, equity curve, fees/drawdown and rejection count.

A backtest interrupted after a simulated fill, serialized to disk, restored into a fresh backtester and completed produces exactly the same `BacktestResult` as an uninterrupted run. Checkpoints are bound to normalized stream content and the strategy/risk/execution configuration.

Checkpoint recovery is hardened beyond schema validation: trade/P&L/position/fee/drawdown chains are checked for internal consistency, pipeline/equity state must match the processed replay prefix, failed restores do not partially mutate an existing session, and an injected atomic-replace failure preserves the last good checkpoint file while cleaning the temporary file.

Strategy identity is explicit in the evaluator contract. The registry provides immutable ID registration, ACTIVE/RETIRED lifecycle, fresh factory resolution and explicit historical resolution of retired versions; factories are revalidated against identity and history semantics.

The regime engine is the first derived research feature with an explicit versioned output contract. Its feature identity is parameter-specific and Decimal-canonical, and outputs carry canonical instrument plus closed-candle `as_of` event-time provenance.

Research reproducibility now also has explicit temporal contracts:

- train/validation/test windows are timezone-aware, half-open, ordered/non-overlapping, allow deliberate gaps, and use a UTC-canonical versioned identity;
- periodic returns require an explicitly declared interval and reject irregular sampling instead of inferring frequency; annualization is optional metadata and is never guessed;
- deterministic rolling walk-forward folds use explicit train length, test length, step and optional embargo, and never emit a truncated final fold.

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
- return calculations reject irregular/non-monotonic observations
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
- deterministic rolling walk-forward fold construction with optional embargo
- event-driven backtester with fees/slippage, risk rejection, no-look-ahead regression, equity curve and core metrics

### Current objective

Deepen failure hardening and reproducible research contracts while preserving canonical mapping and trading-safety boundaries. Validate real provider evidence only where the environment and credentials actually permit it.

Immediate work:

1. Add more persistence/network/provider fault injection around recovery and control-state transitions, but first make first-run initialization versus persisted-state corruption semantics explicit where absence is currently valid.
2. Define OOS evaluation/result provenance contracts before strategy selection or optimization; bind results to strategy identity, feature identity, fold/boundary identity and execution assumptions.
3. Add Sharpe/Sortino or annualized metrics only after exact sample/population conventions are explicit and `periods_per_year` is required rather than inferred.
4. Extend versioned feature-output contracts to the next derived feature only when its event-time/reproducibility boundary is explicit.
5. Validate an actual Dhan compact-master transfer in an environment that supports the provider's octet-stream response; record freshness/evidence without auto-linking instruments.
6. Add optional authenticated historical-provider smoke validation only when credentials/entitlements are explicitly and securely supplied; never commit credentials.

### Engineering gates

Every addition must keep `main` green across Ruff, strict MyPy, PostgreSQL migrations when applicable, the full unit/integration suite, Bandit, migration rollback/reapply, Docker build and runtime smoke.

### Explicitly out of scope for the current phase

- unrestricted live order placement
- any real broker order submission
- broker credentials in source control
- distributed research orchestration before a real workload justifies it
- ML-controlled execution
- profitability claims
- Kubernetes/microservice expansion

### Safety invariant

Live trading remains disabled. No external adapter or future execution path may bypass data quality, canonical instrument mapping, decision, independent risk, OMS, audit, reconciliation, persisted controls, operational health or the explicit live gate.

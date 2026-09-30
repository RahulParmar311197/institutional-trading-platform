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

Strategy identity is explicit in the evaluator contract. The registry provides immutable ID registration, ACTIVE/RETIRED lifecycle, fresh factory resolution and explicit historical resolution of retired versions; factories are revalidated against identity and history semantics.

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
- replay/backtest checkpoint stream/config mismatch and malformed schema fail closed
- runtime container import smoke after production-only dependency install

### Quant/research foundation already validated

- canonical instrument master/provider identifiers and migration `0006` provider classification metadata
- point-in-time/full-range provider reference resolution with missing/overlap/rollover rejection
- read-only Upstox/Dhan HTTP contract clients using mocked transports
- canonical Upstox and Dhan daily services using PostgreSQL identifier resolution plus mocked HTTP
- Dhan compact-master parser, bounded fetcher, conflict-safe synchronizer and transactional refresh
- provider OHLC/provenance/duplicate-timestamp validation and OHLC→closed-candle normalization
- deterministic replay plus atomic local replay checkpoint persistence
- full-state deterministic backtest checkpoint/resume
- configurable sessions, session-aligned multi-timeframe candles, SMA/EMA/RSI/ATR/VWAP
- confirmed swings, BOS/CHoCH, FVG lifecycle, displacement-confirmed MSS and deterministic trend/volatility regime
- versioned EMA crossover identity plus immutable strategy registry/lifecycle
- event-driven backtester with fees/slippage, risk rejection, no-look-ahead regression, equity curve and core metrics

### Current objective

Deepen research reproducibility/failure hardening and versioned feature contracts while preserving canonical mapping and trading-safety boundaries. Validate real provider evidence only where the environment and credentials actually permit it.

Immediate work:

1. Add additional checkpoint/recovery fault injection and internal-state consistency validation before distributed research orchestration.
2. Add broader versioned feature-output contracts on top of the tested strategy registry/lifecycle.
3. Validate an actual Dhan compact-master transfer in an environment that supports the provider's octet-stream response; record freshness/evidence without auto-linking instruments.
4. Add optional authenticated historical-provider smoke validation only when credentials/entitlements are explicitly and securely supplied; never commit credentials.
5. Continue SMC/liquidity concepts only when availability/invalidation rules are objective and regression-testable.
6. Define explicit dataset/period semantics before walk-forward, OOS, Sharpe/Sortino or annualized metrics.

### Engineering gates

Every addition must keep `main` green across Ruff, strict MyPy, PostgreSQL migrations when applicable, the full unit/integration suite, Bandit, migration rollback/reapply, Docker build and runtime smoke.

### Explicitly out of scope for the current phase

- unrestricted live order placement
- any real broker order submission
- broker credentials in source control
- distributed research orchestration before checkpoint recovery is sufficiently hardened
- ML-controlled execution
- profitability claims
- Kubernetes/microservice expansion

### Safety invariant

Live trading remains disabled. No external adapter or future execution path may bypass data quality, canonical instrument mapping, decision, independent risk, OMS, audit, reconciliation, persisted controls, operational health or the explicit live gate.

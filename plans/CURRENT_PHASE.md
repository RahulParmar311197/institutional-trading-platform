# Current Phase

## Phase 5 — Event-driven research, external read-only data and failure hardening

Status: `IN_PROGRESS`

### Validated milestone

The deterministic paper/replay/research vertical slice is green on `main`:

Recorded events / local JSONL / provider historical bars → normalization → closed candles → versioned strategy identity → TradingDecision → independent risk → OMS/paper execution → position/P&L → audit/reconciliation/recovery.

The same strategy/decision/risk contracts power replay-driven paper execution and the event-driven backtester.

Canonical read-only historical slices are validated for Upstox and Dhan cash/derivative daily data. Dhan derivative routing requires explicit persisted provider exchange-segment, instrument-type and expiry-code metadata; identifier rollovers and classification mismatches fail before HTTP.

The Dhan compact instrument-master boundary is also validated end-to-end in CI with mocked HTTP plus real PostgreSQL: exact official URL → bounded streaming retrieval → strict CSV parsing → conflict-safe synchronization → transactional commit. Network fetch/parse completes before the database transaction begins, and synchronization enriches only pre-existing Dhan security-ID links.

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
- Dhan master synchronization pre-validates all conflicts before mutation and never auto-creates canonical instruments
- runtime container import smoke after production-only dependency install

### Quant/research foundation already validated

- canonical instrument master/provider identifiers
- migration `0006` nullable provider classification metadata
- point-in-time/full-range provider reference resolution with missing/overlap/rollover rejection
- read-only Upstox/Dhan HTTP contract clients using mocked transports
- canonical Upstox and Dhan daily services using PostgreSQL identifier resolution plus mocked HTTP
- Dhan compact instrument-master parser for documented supported NSE/BSE equity/F&O rows
- exact-URL, redirect-free, timeout/size-bounded Dhan compact-master fetcher using streamed bytes and UTF-8/BOM handling
- conflict-safe Dhan master synchronizer scoped to incoming security IDs
- transactional Dhan master refresh service that performs network/parse work before opening the database transaction
- provider OHLC/provenance/duplicate-timestamp validation and OHLC→closed-candle normalization
- deterministic replay checkpoints with strict versioned JSON and normalized-stream digest binding
- configurable sessions, session-aligned multi-timeframe candles, SMA/EMA/RSI/ATR/VWAP
- confirmed swings, BOS/CHoCH, FVG lifecycle, displacement-confirmed MSS and deterministic trend/volatility regime
- versioned EMA crossover `v1` strategy identity
- event-driven backtester with fees/slippage, risk rejection, no-look-ahead regression, equity curve and core metrics

### Current objective

Validate real provider evidence where the environment permits it, while continuing research reproducibility and failure hardening without weakening canonical mapping or trading-safety boundaries.

Immediate work:

1. Validate an actual Dhan compact-master transfer in an environment that supports the provider's octet-stream response; record retrieval freshness/evidence without auto-linking instruments.
2. Add optional authenticated historical-provider smoke validation only when credentials/entitlements are explicitly and securely supplied; never commit credentials.
3. Extend replay checkpointing into orchestration-level durable continuation only where long-running replay/backtest jobs actually need it.
4. Add broader feature/strategy output versioning plus registry/lifecycle semantics before scanner work.
5. Continue SMC/liquidity concepts only when availability/invalidation rules are objective and regression-testable.
6. Define explicit dataset/period semantics before walk-forward, OOS, Sharpe/Sortino or annualized metrics.

### Engineering gates

Every addition must keep `main` green across Ruff, strict MyPy, PostgreSQL migrations when applicable, the full unit/integration suite, Bandit, migration rollback/reapply, Docker build and runtime smoke.

### Explicitly out of scope for the current phase

- unrestricted live order placement
- any real broker order submission
- broker credentials in source control
- ML-controlled execution
- profitability claims
- Kubernetes/microservice expansion

### Safety invariant

Live trading remains disabled. No external adapter or future execution path may bypass data quality, canonical instrument mapping, decision, independent risk, OMS, audit, reconciliation, persisted controls, operational health or the explicit live gate.

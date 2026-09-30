# Current Phase

## Phase 5 — Event-driven research, external read-only data and failure hardening

Status: `IN_PROGRESS`

### Validated milestone

The deterministic paper/replay/research vertical slice is green on `main`:

Recorded events / local JSONL / provider historical bars → normalization → closed candles → versioned strategy identity → TradingDecision → independent risk → OMS/paper execution → position/P&L → audit/reconciliation/recovery.

The same strategy/decision/risk contracts power replay-driven paper execution and the event-driven backtester.

Canonical read-only historical slices are validated for Upstox and Dhan cash/derivative daily data. Dhan derivative routing requires explicit persisted provider exchange-segment, instrument-type and expiry-code metadata; identifier rollovers and classification mismatches fail before HTTP.

### Safety controls already validated

- live trading disabled by default
- deny-by-default live-trading policy; no real order adapter
- global/account/strategy/instrument kill switches
- READ_ONLY/CLOSE_ONLY/HALTED operational modes
- persistence/recovery of risk controls and health-driven restrictions
- transactional rollback/no in-memory economic publication on duplicate fill, audit failure or unavailable database
- bounded transient-only provider retries; auth/client failures are not retried
- duplicate historical timestamps fail closed
- invalid Dhan expiry codes/classifications fail before HTTP
- provider-master conflicts are detected before any metadata mutation
- runtime container import smoke after production-only dependency install

### Quant/research foundation already validated

- canonical instrument master/provider identifiers
- migration `0006` nullable provider classification metadata
- point-in-time/full-range provider reference resolution with missing/overlap/rollover rejection
- read-only Upstox/Dhan HTTP contract clients using mocked transports
- canonical Upstox and Dhan daily services using PostgreSQL identifier resolution plus mocked HTTP
- Dhan compact instrument-master parser for documented supported NSE/BSE equity/F&O rows
- conflict-safe Dhan master synchronizer that enriches only pre-existing Dhan security-ID links, never guesses canonical symbol mappings, and scopes queries to incoming security IDs
- provider OHLC/provenance/duplicate-timestamp validation and OHLC→closed-candle normalization
- deterministic replay checkpoints with strict versioned JSON and normalized-stream digest binding
- configurable sessions, session-aligned multi-timeframe candles, SMA/EMA/RSI/ATR/VWAP
- confirmed swings, BOS/CHoCH, FVG lifecycle, displacement-confirmed MSS and deterministic trend/volatility regime
- versioned EMA crossover `v1` strategy identity
- event-driven backtester with fees/slippage, risk rejection, no-look-ahead regression, equity curve and core metrics

### Current objective

Connect verified provider evidence to the tested parsing/synchronization boundary without introducing unsafe auto-linking, then continue research reproducibility and failure hardening.

Immediate work:

1. Add a secure read-only Dhan provider-master retrieval boundary with bounded response size/timeouts and feed its content into the existing parser/synchronizer; never auto-create canonical instruments.
2. Add optional authenticated read-only historical-provider smoke validation only when credentials/entitlements are explicitly and securely supplied; never commit credentials.
3. Extend replay checkpointing into orchestration-level durable continuation only where long-running research/backtest jobs need it.
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

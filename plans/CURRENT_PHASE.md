# Current Phase

## Phase 5 — Event-driven research, external read-only data and failure hardening

Status: `IN_PROGRESS`

### Validated milestone

The deterministic paper/replay/research vertical slice is green on `main`:

Recorded events / local JSONL / provider historical bars → normalization → closed candles → versioned strategy identity → TradingDecision → independent risk → OMS/paper execution → position/P&L → audit/reconciliation/recovery.

The same strategy/decision/risk contracts power replay-driven paper execution and the event-driven backtester.

Canonical read-only historical slices are now validated for:

- Upstox: canonical instrument → full-range dated Upstox identifier → read-only historical client → validated provider bars.
- Dhan daily cash: canonical NSE/BSE cash instrument → full-range dated Dhan security ID → explicit `NSE_EQ`/`BSE_EQ` + `EQUITY` classification → read-only daily client → validated provider bars.

Identifier-rollover ranges are rejected before HTTP. Dhan derivatives are also rejected rather than inferred because the canonical model does not yet encode enough provider-specific derivative classification.

### Safety controls already validated

- live trading disabled by default
- deny-by-default live-trading policy; policy only, no real order adapter
- global/account/strategy/instrument kill switches
- READ_ONLY/CLOSE_ONLY/HALTED operational modes
- close-only position-reduction semantics
- persistence/recovery of active risk controls
- operational health fail-closed gating
- persisted health escalation; healthy status never auto-relaxes restrictive controls
- transaction rollback/no in-memory economic publication on duplicate fill, audit failure or unavailable database
- bounded transient-only provider retries; auth/client failures are not retried
- provider historical responses with duplicate timestamps fail closed
- runtime container import smoke after production-only dependency install

### Quant/research foundation already validated

- canonical instrument master/provider identifiers
- point-in-time and full-range provider-ID resolution with missing/overlap/rollover failure behavior
- recorded event JSONL ingestion and historical-source abstraction
- read-only Upstox/Dhan historical HTTP contract clients using mocked transports
- canonical Upstox historical service using PostgreSQL identifier resolution plus mocked HTTP
- canonical Dhan daily cash service for explicit NSE/BSE cash mappings using PostgreSQL plus mocked HTTP
- provider OHLC/provenance/duplicate-timestamp validation and OHLC→closed-candle normalization
- deterministic replay checkpoints with strict versioned JSON serialization and normalized-stream digest binding
- quote-quality validation
- configurable trading sessions and session-aligned multi-timeframe candles
- SMA/EMA/RSI/ATR/VWAP
- confirmed swings, BOS/CHoCH, FVG lifecycle and displacement-confirmed MSS
- deterministic trend/volatility regime
- versioned EMA crossover `v1` strategy identity persisted through the existing `strategy_id` contract
- event-driven backtester with fees/slippage, risk rejection, no-look-ahead regression, equity curve and core metrics

### Current objective

Deepen read-only provider validation and research reproducibility without weakening canonical mapping or trading-safety boundaries.

Immediate work:

1. Add optional authenticated read-only provider smoke validation only when credentials/entitlements are explicitly and securely supplied; never commit credentials.
2. Define explicit canonical/provider classification metadata before any Dhan futures/options support; do not infer ambiguous provider enums.
3. Extend replay checkpointing into orchestration-level durable continuation only where long-running replay/backtest jobs actually need it.
4. Add broader feature/strategy output versioning plus registry/lifecycle semantics before scanner work.
5. Continue SMC/liquidity concepts only when availability/invalidation rules are objective and regression-testable.
6. Define explicit dataset/period semantics before walk-forward, OOS, Sharpe/Sortino or annualized metrics.

### Engineering gates

Every addition must keep `main` green across:

- Ruff
- strict MyPy
- PostgreSQL migrations when schema changes
- full unit/integration tests
- Bandit
- migration rollback/reapply
- Docker build plus runtime import smoke

### Explicitly out of scope for the current phase

- unrestricted live order placement
- any real broker order submission
- broker credentials in source control
- ML-controlled execution
- profitability claims
- Kubernetes/microservice expansion

### Safety invariant

Live trading remains disabled. No external adapter or future execution path may bypass data quality, canonical instrument mapping, decision, independent risk, OMS, audit, reconciliation, persisted controls, operational health or the explicit live gate.

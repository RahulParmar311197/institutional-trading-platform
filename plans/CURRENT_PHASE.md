# Current Phase

## Phase 5 — Event-driven research, external read-only data and failure hardening

Status: `IN_PROGRESS`

### Validated milestone

The deterministic paper/replay/research vertical slice is green on `main`:

Recorded events / local JSONL / provider historical bars → normalization → closed candles → strategy → TradingDecision → independent risk → OMS/paper execution → position/P&L → audit/reconciliation/recovery.

The same strategy/decision/risk contracts power replay-driven paper execution and the event-driven backtester.

A canonical Upstox historical slice is also validated:

Canonical instrument → full-range dated Upstox identifier resolution → read-only historical client → validated provider bars.

A request that crosses an instrument-identifier rollover is rejected before HTTP rather than silently using one stale ID.

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
- runtime container import smoke after production-only dependency install

### Quant/research foundation already validated

- canonical instrument master/provider identifiers
- point-in-time and full-range provider-ID resolution with missing/overlap/rollover failure behavior
- recorded event JSONL ingestion and historical-source abstraction
- read-only Upstox/Dhan historical HTTP contract clients using mocked transports
- canonical Upstox historical service using PostgreSQL identifier resolution plus mocked HTTP
- bounded transient-only read retries; auth/client failures are not retried
- provider OHLC/provenance validation and OHLC→closed-candle normalization
- quote-quality validation
- configurable trading sessions and session-aligned multi-timeframe candles
- SMA/EMA/RSI/ATR/VWAP
- confirmed swings, BOS/CHoCH, FVG lifecycle and displacement-confirmed MSS
- deterministic trend/volatility regime
- event-driven backtester with fees/slippage, risk rejection, no-look-ahead regression, equity curve and core metrics

### Current objective

Complete the read-only historical boundary without guessing provider classification, while continuing failure hardening and research reproducibility.

Immediate work:

1. Define a safe canonical Dhan historical service only after the required exchange-segment/instrument classification can be derived from explicit canonical metadata; do not guess provider enums.
2. Add resume/interruption semantics where historical/replay work needs deterministic continuation rather than implicit restart.
3. Add secure optional authenticated read-only provider smoke validation only when credentials are explicitly supplied; never commit credentials.
4. Add feature/strategy output versioning before scanner work.
5. Continue SMC/liquidity concepts only when availability/invalidation rules are objective and testable.

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

# Current Phase

## Phase 5 — Event-driven research and failure hardening

Status: `IN_PROGRESS`

### Validated milestone

The deterministic paper/replay/research vertical slice is green in CI:

Recorded events / JSONL historical source → normalization/replay → closed candles → strategy → TradingDecision → independent risk → OMS/paper execution → position/P&L → audit/reconciliation/recovery.

The same strategy/decision/risk contracts now power both replay-driven paper execution and the minimal event-driven backtester.

### Safety controls already validated

- live trading disabled by default
- global/account/strategy/instrument kill switches
- READ_ONLY/CLOSE_ONLY/HALTED operational modes
- close-only position-reduction semantics
- persistence/recovery of active risk controls
- operational health gate that fails closed to READ_ONLY/HALTED
- transaction rollback when audit persistence fails, with no partial order/fill state or in-memory economic publication

### Quant/research foundation already validated

- canonical instrument master/provider identifiers
- recorded event JSONL ingestion and historical-source abstraction
- quote-quality validation
- configurable trading sessions
- session-anchored multi-timeframe candles
- SMA/EMA/RSI/ATR/VWAP
- confirmed swing and structure-break detection
- trend state with BOS continuation and CHoCH transition semantics
- deterministic LOW/NORMAL/HIGH ATR-ratio volatility regime
- three-candle FVG detection and open/partial/filled/invalidated lifecycle
- reusable deterministic replay strategy pipeline
- minimal event-driven backtester with explicit slippage/fee assumptions, independent risk rejection, deterministic repeatability and future-event isolation

### Current objective

Deepen the research engine without diverging from production-style contracts.

Immediate work:

1. Add an explicit backtest equity curve and deterministic core metrics such as return, maximum drawdown and trade statistics.
2. Define MSS separately from CHoCH using explicit confirmation/availability/invalidation semantics before coding it.
3. Add focused failure tests for database connectivity/provider interruption and persisted operational-mode transitions.
4. Verify current official Upstox/Dhan historical-data APIs before adding authenticated provider adapters.

### Engineering gates

Every addition must keep `main` green across:

- Ruff
- strict MyPy
- PostgreSQL migrations when schema changes
- full unit/integration tests
- Bandit
- migration rollback/reapply
- Docker build

### Explicitly out of scope for the current phase

- unrestricted live order placement
- real broker order submission
- broker credentials in source control
- ML-controlled execution
- profitability claims
- Kubernetes/microservice expansion

### Safety invariant

Live trading remains disabled. No future external adapter or execution path may bypass data quality, decision, independent risk, OMS, audit, reconciliation, persisted operational controls or health gating.
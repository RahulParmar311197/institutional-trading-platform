# Current Phase

## Phase 3/5 — Deterministic quant foundation into event-driven research

Status: `IN_PROGRESS`

### Validated milestone

The deterministic paper/replay vertical slice is green in CI:

Recorded market events → normalization/replay → closed candles → strategy → TradingDecision → independent risk → OMS → transactional durable paper execution → fill → position/P&L → audit → reconciliation → restart recovery.

Validated safety controls now include global/account/strategy/instrument kill switches, READ_ONLY/CLOSE_ONLY/HALTED operational modes, close-only position-reduction semantics, and persistence/recovery of active risk controls.

### Quant foundation already validated

- canonical instrument master/provider identifiers
- quote-quality validation
- configurable trading sessions
- session-anchored multi-timeframe candles
- SMA/EMA/RSI/ATR/VWAP
- confirmed swing and structure-break detection
- trend state with BOS continuation and CHoCH transition semantics
- three-candle FVG detection and open/partial/filled/invalidated lifecycle
- reusable deterministic replay strategy pipeline

### Current objective

Build the first minimal event-driven backtesting layer on top of the same replay/strategy/decision/risk contracts already used by paper execution.

The backtester must explicitly model its assumptions rather than silently granting ideal fills. Initial scope should include:

- replay-driven chronological processing
- deterministic strategy decisions from closed candles only
- independent risk approval/rejection
- explicit market-fill model
- spread/slippage and fee hooks with safe zero defaults only when clearly configured
- positions, realized/unrealized P&L and equity progression
- deterministic repeatability tests
- no-look-ahead regression tests

### Engineering gates

Every addition must keep `main` green across:

- Ruff
- strict MyPy
- PostgreSQL migrations when schema changes
- full unit/integration tests
- Bandit
- migration rollback/reapply
- Docker build

### After the minimal backtester

1. Add deterministic regime primitives.
2. Expand SMC only with explicit/testable availability and invalidation semantics.
3. Strengthen failure injection and operational health gating.
4. Introduce provider-neutral read-only historical adapters after verifying current official provider APIs.
5. Keep all real broker order submission disabled until live-trading safety gates are complete and explicitly approved.

### Explicitly out of scope for the current phase

- unrestricted live order placement
- real broker order submission
- broker credentials in source control
- ML-controlled execution
- profitability claims
- Kubernetes/microservice expansion

### Safety invariant

Live trading remains disabled. No future broker adapter may bypass data-quality, decision, independent risk, OMS, audit, reconciliation or persisted operational controls.
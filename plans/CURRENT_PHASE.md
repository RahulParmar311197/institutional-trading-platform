# Current Phase

## Phase 2/3 — Market-data and deterministic quant foundation

Status: `IN_PROGRESS`

### Completed foundation milestone

The first deterministic paper-trading vertical slice is green in CI:

Market/feature inputs → strategy signal → TradingDecision → independent risk → OMS → transactional durable paper execution → fill → position/P&L → audit → reconciliation → restart recovery.

Validated infrastructure includes PostgreSQL migrations/integration tests, Docker build, strict typing, lint and Bandit.

### Current objective

Build the data/quant layer required for trustworthy research and replay before adding real broker execution:

- provider-neutral recorded/historical market-data ingestion
- explicit event timestamps/provenance
- configurable exchange/session calendar boundaries
- session-aware multi-timeframe candles
- deterministic technical/price-action/SMC primitives
- replay-compatible interfaces
- data-quality gates

### Already validated in this phase

- canonical instrument master/provider identifiers
- quote-quality validation
- configurable trading sessions
- session-anchored multi-timeframe candles
- SMA/EMA/RSI/ATR/VWAP
- confirmed swing detection with explicit confirmation timing
- deterministic structure-break detection
- deterministic three-candle FVG detection using closed candles only

### Immediate engineering gates

Every addition must keep `main` green across:

- Ruff
- strict MyPy
- migrations against PostgreSQL when schema changes
- unit/integration tests
- Bandit
- migration rollback/reapply
- Docker build

### Next vertical work

Recorded market events → normalization/data-quality → replay clock/event stream → candles/features → strategy/decision/risk → existing durable paper path.

In parallel, extend market structure conservatively: CHoCH/MSS/FVG lifecycle only after their deterministic availability and invalidation semantics are explicitly encoded and tested.

### Explicitly out of scope for this phase

- unrestricted live order placement
- real broker order submission
- broker credentials in source control
- ML-controlled execution
- profitability claims
- Kubernetes/microservice expansion

### Safety invariant

Live trading remains disabled. No broker adapter may bypass data-quality, decision, risk, OMS, audit or reconciliation controls.
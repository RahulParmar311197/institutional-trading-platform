# Current Phase

## Phase 1 stabilization + first paper-trading vertical slice

Status: `IN_PROGRESS`

### Current objective

Get the existing foundation green in CI, then complete the smallest deterministic end-to-end paper path before adding broader strategy/SMC/options/ML scope.

### Implemented but still under validation

- Python 3.12 project/tooling
- FastAPI application
- fail-safe typed settings (`live_trading_enabled=false` by default)
- PostgreSQL async boundary + Alembic
- Redis readiness boundary
- liveness/readiness endpoints
- audit-event persistence foundation
- Docker/Compose
- GitHub Actions CI
- canonical instrument master/provider identifiers
- quote-quality validation
- deterministic candle builder
- SMA/EMA/RSI
- strategy signal contract and EMA crossover baseline
- independent pre-trade notional risk checks
- OMS state machine with fill idempotency
- deterministic paper market execution and position tracking

### Immediate engineering gate

CI must pass:

- Ruff
- MyPy
- Pytest
- Bandit
- Docker build

No component moves to `TESTED` until the relevant checks actually pass.

### Next vertical-slice work

Decision contract → persistent OMS/order/fill schema → paper P&L → reconciliation → journal/audit → end-to-end paper workflow test.

### Explicitly out of scope for this phase

- unrestricted live order placement
- broker credentials in source control
- ML-controlled execution
- profitability claims
- broad strategy catalog
- Kubernetes/microservice expansion

### Safety invariant

Live trading remains disabled and cannot be treated as complete or production-ready until all live gates, reconciliation and explicit operator approval exist.
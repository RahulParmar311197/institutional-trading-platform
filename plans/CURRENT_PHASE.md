# Current Phase

## Phase 1 — Foundation

Status: `IN_PROGRESS`

### Objective

Create the smallest runnable, testable and secure platform foundation on which trading-critical vertical slices can be built.

### Scope

- Python 3.12+ project configuration
- FastAPI application
- typed environment/configuration model
- domain package boundaries
- PostgreSQL + SQLAlchemy 2
- Alembic migrations
- Redis connectivity abstraction
- structured application logging
- health/liveness/readiness endpoints
- audit-event foundation
- Dockerfile + Docker Compose
- Ruff, MyPy, Pytest and Bandit configuration
- GitHub Actions CI
- `.env.example` without secrets
- initial architecture/testing/security documentation

### Explicitly out of scope

- real order placement
- live-trading enablement
- strategy profitability claims
- ML order decisions
- fake broker integrations

### Exit gate

Phase 1 is not complete until:

- application imports/starts successfully
- formatting/lint passes
- static type checks pass at configured scope
- unit tests pass
- integration tests for critical foundation boundaries pass
- migrations can be applied from a clean database
- Docker images build
- health/readiness behavior is tested
- secret/security scans have no unresolved critical findings
- `docs/IMPLEMENTATION_STATUS.md` reflects evidence

### Next

Proceed to Phase 2: canonical instrument master, historical/live market-data boundaries and data-quality pipeline.
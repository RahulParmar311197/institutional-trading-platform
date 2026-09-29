# Next Tasks

Tasks are ordered. Do not skip critical validation to work on optional features.

## P0 — Phase 1 foundation

1. Create `pyproject.toml` with pinned-compatible backend/tooling dependencies and Python 3.12 baseline.
2. Create backend package/application structure without empty speculative modules.
3. Implement typed settings with explicit environment and `live_trading_enabled=false` default.
4. Implement FastAPI app factory plus `/health/live` and `/health/ready`.
5. Add SQLAlchemy async database boundary and Alembic.
6. Add Redis health/connectivity boundary.
7. Add structured logging and request/trace correlation foundation.
8. Add initial append-oriented audit-event model/migration.
9. Add unit/integration tests for settings, health and dependency failures.
10. Add Dockerfile and Docker Compose for API/PostgreSQL/Redis.
11. Add Ruff, MyPy, Pytest and Bandit checks.
12. Add GitHub Actions CI.
13. Add `.env.example`, `.gitignore`, security and developer setup documentation.
14. Run/verify all available checks; fix failures rather than weakening tests.
15. Update `docs/IMPLEMENTATION_STATUS.md` with actual evidence.

## P1 — First trading vertical slice after foundation

Instrument master → recorded/historical market data → validation → candle aggregation → indicators → deterministic SMC/ICT → strategy → decision → risk → OMS → paper broker → fill → position/P&L → reconciliation → journal → API/UI → E2E.

## Constraints

- No live execution during Phase 1.
- No hardcoded success responses representing real integrations.
- No secrets in repository.
- No broad placeholder package generation merely to make the tree look complete.
- A feature remains unverified until its required tests/checks have run successfully.
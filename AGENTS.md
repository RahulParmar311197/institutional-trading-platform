# AGENTS.md

## Mission

Build the smallest correct, secure, maintainable and verifiable institutional trading platform that satisfies `docs/MASTER_BLUEPRINT.md`.

This repository is an execution project, not a prompt/demo repository.

## Required workflow

For every meaningful task:

Understand → Inspect → Research → Design → Implement → Run → Lint → Type-check → Test → Fix → Security-check → Validate → Document → Continue

Before editing:

1. Inspect existing code and configuration.
2. Read `docs/MASTER_BLUEPRINT.md`.
3. Read `docs/IMPLEMENTATION_STATUS.md`.
4. Read `plans/CURRENT_PHASE.md` and `plans/NEXT_TASKS.md`.
5. Preserve working implementation instead of rebuilding unnecessarily.

## Priority

1. Broken build
2. Security/data-loss/trading-safety risks
3. Failing tests
4. Critical end-to-end workflows
5. Real integrations
6. Required features
7. Performance
8. UX
9. Optional improvements

## Vertical slices

Prefer complete slices:

Database → Domain → Service → API → UI (when required) → Tests → Observability → Documentation

Do not create large forests of empty interfaces/placeholders.

## Verification

Generated code is `IMPLEMENTED_UNVERIFIED` until verified.

Where applicable run:

- formatting
- lint
- static typing
- unit tests
- integration tests
- migrations
- security checks
- dependency checks
- build
- critical E2E workflows

Never weaken valid tests merely to make CI green.

## Trading safety invariants

- Live trading is disabled by default.
- No LLM or ML model directly submits orders.
- Every live order must pass deterministic decision, independent risk, execution policy and OMS controls.
- No strategy may bypass the risk engine.
- No order may bypass the OMS.
- Reconciliation must complete before live trading after restart.
- A global kill switch prevents new live orders.
- Stale/invalid market data can block trading.
- Broker timeouts must not cause blind duplicate submissions.
- Order/fill processing must be idempotent.
- Historical calculations must prevent look-ahead.
- Historical SMC/ICT signals must not repaint.
- Demo/mock data must never be silently represented as live.
- Money/accounting values use exact decimal semantics where required.
- Never commit broker tokens, passwords, API secrets or production credentials.

## Backtest integrity

Prevent:

- look-ahead bias
- survivorship bias where applicable
- leakage
- impossible fills
- ignored transaction costs
- accidental use of incomplete future candles

Backtest, paper and live modes should reuse strategy/decision/risk interfaces whenever practical.

## Status discipline

Maintain `docs/IMPLEMENTATION_STATUS.md` using:

- NOT_STARTED
- IN_PROGRESS
- IMPLEMENTED_UNVERIFIED
- TESTED
- BLOCKED
- PRODUCTION_VALIDATED

Never mark functionality TESTED without evidence.
Never mark functionality PRODUCTION_VALIDATED from unit tests alone.

After each major milestone update:

- completed work
- validation evidence
- remaining work
- blockers
- next highest-priority task

## Architecture

Start with a modular monolith plus workers. Do not introduce microservices, Kubernetes, Kafka or equivalent complexity without demonstrated requirements.

Initial stack target:

- Python 3.12+
- FastAPI / Pydantic v2 / SQLAlchemy 2 / Alembic
- PostgreSQL / TimescaleDB / Redis
- NumPy / Polars; Pandas where appropriate
- Next.js / React / TypeScript
- Docker / Docker Compose
- Pytest / Ruff / MyPy / Bandit
- Vitest / Playwright
- OpenTelemetry / Prometheus / Grafana

## Completion rule

Code generation alone is never completion.

A trading-critical feature requires implementation + tests + error handling + observability + security + auditability + recovery/idempotency where relevant + documentation.
# Architecture Decisions

## ADR-001 — Modular monolith first

**Decision:** Start with a modular monolith plus background workers.

**Reason:** It minimizes distributed-system complexity while preserving clear domain boundaries. Services may be extracted only when throughput, reliability or organizational constraints justify them.

## ADR-002 — Independent deterministic risk

**Decision:** Strategies/AI produce intent or evidence; a deterministic independent risk layer controls whether an order can proceed.

**Reason:** Trading safety cannot depend on probabilistic model behavior.

## ADR-003 — Live disabled by default

**Decision:** Live execution requires explicit multi-gate enablement and successful reconciliation.

**Reason:** A configuration error must fail safe rather than create economic exposure.

## ADR-004 — Shared interfaces across backtest/paper/live

**Decision:** Reuse strategy, decision and risk contracts across execution modes where practical.

**Reason:** Reduces behavioral drift between research and production.

## ADR-005 — PostgreSQL is durable trading truth

**Decision:** Critical orders, fills, positions, risk decisions and audit state are durable in PostgreSQL. Redis is not the sole source of truth.

**Reason:** Critical state must survive cache loss/restarts and support transactional consistency/reconciliation.

## ADR-006 — Broker-neutral core

**Decision:** Canonical instruments/orders/positions remain independent of Upstox/Dhan identifiers and payloads.

**Reason:** Avoids vendor lock-in and keeps testing/replay/paper/live behavior consistent.

## ADR-007 — Evidence-based implementation status

**Decision:** Generated code is `IMPLEMENTED_UNVERIFIED` until required validation has actually run.

**Reason:** Prevents project-control documents from overstating readiness.
# Implementation Status

Last updated: 2026-09-30

This file is the source of truth for implementation status. Generated code alone does not count as working functionality.

## Status definitions

- `NOT_STARTED` — no implementation exists.
- `IN_PROGRESS` — implementation is partial or required validation remains incomplete.
- `IMPLEMENTED_UNVERIFIED` — implementation exists but its required validation has not passed.
- `TESTED` — required automated validation has passed for the stated scope.
- `BLOCKED` — progress requires a named external dependency or decision.
- `PRODUCTION_VALIDATED` — validated in the intended production-like environment; CI alone cannot establish this.

## Repository control

| Capability | Status | Evidence / notes |
|---|---|---|
| Master/full blueprint | IMPLEMENTED_UNVERIFIED | `docs/MASTER_BLUEPRINT.md`, `docs/FULL_PROJECT_BLUEPRINT.md` |
| AI/agent execution rules | IMPLEMENTED_UNVERIFIED | `AGENTS.md` |
| Implementation tracking | IN_PROGRESS | This file is maintained during coding cycles |
| Current phase tracking | IN_PROGRESS | `plans/CURRENT_PHASE.md` |
| Next task tracking | IN_PROGRESS | `plans/NEXT_TASKS.md` |

## Platform capabilities

| Capability | Status | Evidence / notes |
|---|---|---|
| Python/FastAPI foundation | TESTED | Ruff, strict MyPy, Pytest, Bandit and Docker pass on `main` |
| Typed configuration | TESTED | live trading defaults off; enabling outside LIVE is rejected |
| PostgreSQL/SQLAlchemy/Alembic | TESTED | migrations 0001-0005 apply, downgrade to base and reapply against PostgreSQL |
| Redis | TESTED | real Redis readiness integration coverage in CI |
| Structured logging/request correlation | TESTED | request-ID generation/preservation covered |
| Health/readiness | TESTED | liveness and fail-closed database/Redis readiness covered |
| Docker runtime | TESTED | image builds after runtime-only install and imports app/provider modules |
| CI | TESTED | cumulative `main` run `36694395696` completed successfully |
| Instrument master | TESTED | canonical instrument/provider identifier schema and migration validation |
| Provider identifier resolver | TESTED | point-in-time and full-range provider IDs resolve deterministically; missing, overlapping and rollover-crossing mappings fail closed |
| Recorded market events | TESTED | provider-neutral recorded trade envelope, timestamps, ordering, dedupe/conflict checks |
| Recorded JSONL ingestion | TESTED | Decimal/timestamp round-trip, normalization and malformed-input rejection |
| Provider-neutral historical source | TESTED | local JSONL source, filtering and multi-source normalization |
| Provider historical OHLC model | TESTED | timezone/provenance/positive-price/OHLC coherence/volume/OI invariants covered |
| Provider response uniqueness | TESTED | Upstox and Dhan responses with duplicate candle timestamps are rejected before normalization/research |
| Historical provider normalization | TESTED | provider OHLCV bars convert to canonical closed candles without inventing trades |
| Upstox historical read-only client | TESTED | V3 request shape represented; exact URL/auth/header/response behavior covered with `httpx.MockTransport` only |
| Canonical Upstox historical service | TESTED | canonical instrument→full-range provider ID→read-only client path tested; rollover-crossing range rejected before HTTP |
| Dhan historical read-only client | TESTED | v2 daily/intraday request/response shapes represented and covered with `httpx.MockTransport` only |
| Canonical Dhan daily cash service | TESTED | canonical NSE/BSE cash instrument→full-range Dhan security ID→`NSE_EQ`/`BSE_EQ` + `EQUITY`→daily read-only client; rollover and unsupported derivatives fail before HTTP |
| Dhan derivatives canonical mapping | NOT_STARTED | canonical model does not yet carry enough provider-specific instrument classification; no guessing is allowed |
| Authenticated external historical ingestion | IN_PROGRESS | client/service contracts exist; no real credentialed provider call has been claimed or validated |
| Historical read retry policy | TESTED | bounded retry for transport errors and transient HTTP statuses; auth/client errors do not retry |
| Live market data | NOT_STARTED | provider WebSocket ingestion pending |
| Data quality | TESTED | stale/crossed/future/non-positive quotes plus historical OHLC/duplicate-timestamp checks covered |
| Session model | TESTED | configurable timezone/open/close sessions and session-aligned buckets |
| Multi-timeframe candles | TESTED | session-anchored aggregation, session-close truncation and outside-session rejection |
| Indicators | TESTED | SMA, EMA, RSI, ATR and VWAP deterministic coverage |
| Price action | TESTED | confirmed swings and structure breaks with explicit confirmation timing |
| Market structure | TESTED | event-time BOS continuation and opposite-direction CHOCH transitions |
| FVG lifecycle | TESTED | deterministic bullish/bearish FVG open/partial/filled/invalidated lifecycle |
| MSS | TESTED | CHOCH is not aliased to MSS; MSS additionally requires direction-aligned ATR-based displacement using only available candles |
| SMC/ICT broader layer | IN_PROGRESS | FVG and MSS tested; blocks/liquidity concepts remain pending |
| Regime engine | TESTED | deterministic trend + ATR-ratio LOW/NORMAL/HIGH volatility regime |
| Strategy framework | IN_PROGRESS | protocol/history contract + versioned EMA crossover `v1` identity tested; registry/lifecycle/broader feature versioning pending |
| Decision engine | TESTED | explicit TradingDecision contract and fail-closed invalid-price/no-direction behavior |
| Scanner | NOT_STARTED | later phase |
| Replay | TESTED | normalized deterministic event stream and event→closed-candle→strategy→decision pipeline |
| Replay checkpoint/resume | TESTED | versioned JSON checkpoint binds cursor/event count to SHA-256 digest of normalized stream; changed datasets/counts/malformed state fail closed |
| Replay → durable paper integration | TESTED | replay decision reaches transactional durable paper persistence |
| Event-driven backtester | TESTED | production-style replay/strategy/decision/risk/paper contracts, explicit fees/slippage, risk rejection and future-event isolation |
| Backtest core analytics | TESTED | event-time equity curve, total return, max drawdown, trade counts, realized wins/losses, gross P/L and profit factor |
| Walk-forward/OOS/Monte Carlo | NOT_STARTED | later phase |
| OMS | TESTED | state transitions, fill caps, duplicate-fill idempotency and recovered state |
| Durable order/fill persistence | TESTED | decision linkage, deduplication, persistence and recovery |
| Paper broker | TESTED | deterministic market fill and position updates |
| Durable paper execution | TESTED | order/fill/audit commit precedes in-memory publication; duplicate/audit/DB-unavailable failures fail closed |
| Portfolio/P&L | TESTED | realized/unrealized P&L, partial close, reversal and durable rebuild |
| Journal/audit | TESTED | append-only journal behavior and idempotent AuditEvent persistence |
| Independent risk engine | TESTED | TradingDecision-only path, notional gates and operational controls |
| Kill switches | TESTED | global/account/strategy/instrument locks and READ_ONLY/CLOSE_ONLY/HALTED semantics |
| Persistent risk controls | TESTED | active lock/mode state persists and recovers across process restart |
| Operational health gate | TESTED | missing/critical-unavailable health halts; degraded/noncritical unavailable forces READ_ONLY |
| Persisted health escalation | TESTED | health-driven restriction persists; persistence failure retains restrictive in-memory mode; healthy state never auto-relaxes operator controls |
| Live-trading gate policy | TESTED | deny-by-default policy requires explicit approval, authorization, broker auth, reconciliation, strategy/capital approval, healthy subsystems and normal unlocked controls |
| Reconciliation | TESTED | position quantity/average-price match/mismatch behavior |
| Restart recovery | TESTED | OMS state, processed fills, paper position and risk controls reconstruct from PostgreSQL |
| Real broker order adapter | NOT_STARTED | no order-submission API exists |
| Real execution/reconciliation | NOT_STARTED | paper path only |
| Options engine | NOT_STARTED | later phase |
| ML subsystem | NOT_STARTED | later phase |
| Next.js frontend | NOT_STARTED | later phase |
| Paper E2E workflow | TESTED | decision → risk → OMS → paper fill → position → reconciliation plus replay→durable-paper |
| Failure/security validation | IN_PROGRESS | Bandit green; rollback, DB-unavailable, restart, transient provider failure, provider-response uniqueness, replay checkpoint integrity and persisted health-escalation cases covered; broader fault matrix pending |
| Controlled live release | NOT_STARTED | live remains disabled and is not approved |

## Validation evidence

A green cumulative `main` CI run completed for commit `99b37b12aeb898b5d46a723c7586213f441d129e` in GitHub Actions run `36694395696`.

The run passed, in one workflow:

- dependency installation
- Ruff
- strict MyPy
- PostgreSQL migrations through `0005`
- full Pytest suite including PostgreSQL and Redis integration tests
- Bandit
- Alembic downgrade-to-base and reapply-to-head
- Docker image build
- runtime-only package smoke imports

Validated additions in this milestone include:

- canonical Dhan daily cash service for explicit NSE/BSE cash classifications, with real PostgreSQL identifier resolution and mocked provider HTTP
- Dhan identifier-rollover and derivative-classification fail-closed behavior before HTTP
- deterministic replay checkpoint/resume bound to the normalized event stream
- strict versioned JSON checkpoint serialization and malformed/future/mismatched state rejection
- duplicate provider candle timestamp rejection for Upstox and Dhan
- versioned EMA crossover strategy identity (`ema_crossover_v1_<fast>_<slow>`) carried through the existing `strategy_id` contract without a schema migration

The previously validated research/paper/safety capabilities remain covered by the same cumulative run.

## Important validation boundaries

- Provider HTTP contract/service tests are mocked. They do **not** prove current credentials, entitlements, provider availability or end-to-end authenticated data retrieval.
- Canonical Upstox and Dhan services are integration-tested against PostgreSQL plus mocked HTTP, not real provider accounts.
- The canonical Dhan service currently supports daily NSE/BSE cash equities only. Futures/options are deliberately rejected until explicit canonical/provider instrument classification exists.
- Replay checkpoints are serializable/restart-safe state objects; no external checkpoint store or distributed job runner is claimed.
- No real broker order endpoint is implemented or called.
- CI validates repository/container behavior, not a deployed environment.
- Backtest results are deterministic research outputs, not profitability claims.
- Live trading remains disabled and unapproved.

## Highest-priority work

1. Add optional authenticated read-only provider smoke validation only when credentials/entitlements are securely supplied at runtime; never commit secrets.
2. Define explicit provider instrument-classification metadata before enabling canonical Dhan futures/options or other ambiguous classifications; do not infer them from insufficient fields.
3. Extend checkpoint/resume from replay-stream state into long-running replay/backtest orchestration only where durable continuation is actually needed.
4. Add broader feature/strategy output versioning and registry/lifecycle semantics before scanner work.
5. Continue SMC only with objective/testable liquidity concepts; add walk-forward/OOS only after dataset boundaries and period semantics are explicit.
6. Keep all broker order submission out of scope until every live gate is integrated, validated and explicitly approved.

## Blockers

No blocker for continued research/paper development. Real authenticated historical-provider validation requires user-supplied credentials/entitlements through secure runtime configuration. Dhan derivatives require explicit canonical/provider classification metadata before implementation. Live trading remains deliberately unavailable and no broker order execution has been introduced.

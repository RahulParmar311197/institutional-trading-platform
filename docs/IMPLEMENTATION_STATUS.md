# Implementation Status

Last updated: 2026-09-30

This file is the source of truth for implementation status. Generated code alone does not count as working functionality.

## Status definitions

- `NOT_STARTED` — no implementation exists.
- `IN_PROGRESS` — implementation is partial or required validation remains incomplete.
- `IMPLEMENTED_UNVERIFIED` — implementation exists but required real-context validation has not passed.
- `TESTED` — required automated validation has passed for the stated scope.
- `BLOCKED` — progress requires a named external dependency or decision.
- `PRODUCTION_VALIDATED` — validated in the intended production-like environment; CI alone cannot establish this.

## Repository control

| Capability | Status | Evidence / notes |
|---|---|---|
| Master/full blueprint | IMPLEMENTED_UNVERIFIED | `docs/MASTER_BLUEPRINT.md`, `docs/FULL_PROJECT_BLUEPRINT.md` |
| AI/agent execution rules | IMPLEMENTED_UNVERIFIED | `AGENTS.md` |
| Implementation/current-phase/next-task tracking | IN_PROGRESS | This file plus `plans/CURRENT_PHASE.md` and `plans/NEXT_TASKS.md` are maintained during coding cycles |
| CI | TESTED | latest code-bearing cumulative `main` run `36712796063` completed successfully for commit `17e878e8159168cfa273b21149ebea5693d9d13b` |

## Foundation and infrastructure

| Capability | Status | Evidence / notes |
|---|---|---|
| Python/FastAPI foundation | TESTED | Ruff, strict MyPy, Pytest, Bandit and Docker pass on `main` |
| Typed configuration | TESTED | live trading defaults off; enabling outside LIVE is rejected |
| PostgreSQL/SQLAlchemy/Alembic | TESTED | migrations `0001`-`0007` apply, downgrade to base and reapply against PostgreSQL |
| Redis | TESTED | real Redis readiness integration coverage in CI |
| Structured logging/request correlation | TESTED | request-ID generation/preservation covered |
| Health/readiness | TESTED | liveness and fail-closed database/Redis readiness covered |
| Docker runtime | TESTED | image builds after runtime-only install and imports application/provider modules |

## Instruments and provider data

| Capability | Status | Evidence / notes |
|---|---|---|
| Instrument master | TESTED | canonical instrument/provider identifier schema and migration validation |
| Provider identifier classification metadata | TESTED | migration `0006` adds nullable provider exchange-segment/instrument-type/expiry-code fields without breaking existing identifiers |
| Provider identifier resolver | TESTED | point-in-time/full-range references resolve external ID plus provider metadata; missing, overlapping and rollover-crossing mappings fail closed |
| Dhan compact-master parser/synchronizer | TESTED | strict exchange/segment/instrument/expiry validation, duplicate-security-ID conflict detection; sync updates only existing Dhan links and never symbol-guesses canonical instruments |
| Dhan compact-master retrieval boundary | TESTED | exact official compact URL pinned, redirects disabled, timeout/byte cap enforced, streamed UTF-8/BOM handling; HTTP behavior tested with `httpx.MockTransport` |
| Dhan transactional master refresh | TESTED | fetch/parse precedes PostgreSQL transaction; conflict-safe synchronization commits atomically and persistence is verified from a fresh session |
| Real Dhan compact-master transfer | IMPLEMENTED_UNVERIFIED | retrieval code exists; no successful live octet-stream transfer has been validated in this environment |
| Recorded market events / JSONL | TESTED | provider-neutral trade envelope, timezone/ordering/dedupe/conflict invariants and Decimal/timestamp round-trip |
| Provider-neutral historical source | TESTED | local JSONL filtering and multi-source normalization |
| Provider historical OHLC model/normalization | TESTED | timezone/provenance/positive-price/OHLC/volume/OI invariants and canonical closed-candle conversion |
| Provider response uniqueness | TESTED | duplicate Upstox/Dhan candle timestamps are rejected before normalization/research |
| Upstox historical read-only client/service | TESTED | V3 request/auth/response behavior plus canonical instrument→full-range provider-ID orchestration tested with mocked HTTP and PostgreSQL |
| Dhan historical read-only client/service | TESTED | v2 daily/intraday contracts; daily cash and FUTIDX/FUTSTK/OPTIDX/OPTSTK routing require explicit persisted classification; mocked HTTP + PostgreSQL coverage |
| Authenticated external historical ingestion | IN_PROGRESS | client/service contracts exist; no real credentialed provider call or entitlement validation is claimed |
| Historical read retry policy | TESTED | bounded retry for transport/transient HTTP failures; auth/client errors do not retry |
| Live market data | NOT_STARTED | provider WebSocket ingestion pending |

## Market processing, features and strategy

| Capability | Status | Evidence / notes |
|---|---|---|
| Data quality | TESTED | stale/crossed/future/non-positive quotes plus historical OHLC/duplicate-timestamp checks |
| Session and multi-timeframe candles | TESTED | timezone-aware configurable sessions, session-aligned aggregation, session-close truncation and outside-session rejection |
| Indicators | TESTED | SMA, EMA, RSI, ATR and VWAP deterministic coverage |
| Price action / market structure | TESTED | confirmed swings, BOS continuation and opposite-direction CHOCH with explicit event-time confirmation |
| FVG lifecycle / MSS | TESTED | deterministic FVG open/partial/filled/invalidated lifecycle; MSS requires direction-aligned ATR displacement and is not aliased to CHOCH |
| Broader SMC/ICT layer | IN_PROGRESS | FVG and MSS tested; selected blocks/liquidity concepts remain pending |
| Regime engine / versioned output | TESTED | deterministic trend + ATR-ratio regime; parameter-specific `v1` feature identity carries instrument and closed-candle `as_of` provenance |
| Broader feature-output versioning | IN_PROGRESS | regime is versioned; extend only where derived-feature event-time/reproducibility boundaries are explicit |
| Strategy identity/registry lifecycle | TESTED | stable strategy IDs; EMA crossover parameter-specific `v1` IDs; immutable registration, fresh factory resolution, retirement/history revalidation |
| Strategy framework | IN_PROGRESS | identity and lifecycle tested; additional strategies remain pending |
| Decision engine | TESTED | explicit `TradingDecision` contract and fail-closed invalid-price/no-direction behavior |
| Scanner | NOT_STARTED | later phase |

## Replay, backtesting and research

| Capability | Status | Evidence / notes |
|---|---|---|
| Replay | TESTED | normalized deterministic event stream and event→closed-candle→strategy→decision pipeline |
| Replay checkpoint/resume + file persistence | TESTED | cursor/event count bound to normalized-stream SHA-256; bounded UTF-8 atomic file storage with fsync; changed/malformed state fails closed |
| Event-driven backtester | TESTED | shared replay/strategy/decision/risk/paper contracts, explicit fees/slippage, risk rejection and future-event isolation |
| Backtest durable continuation | TESTED | full-state checkpoint persists replay/pipeline/economic state; fresh-session resume after simulated fill matches uninterrupted result |
| Backtest configuration/integrity/atomic restore | TESTED | strategy/config/risk/control binding, cross-field economic consistency, replay-prefix validation and failed-restore atomicity |
| Backtest checkpoint file persistence | TESTED | secure temp creation, fsync and atomic replace; injected replace failure preserves last good checkpoint |
| Backtest analytics | TESTED | event-time equity curve, total return, max drawdown, trades, realized wins/losses, gross P/L and profit factor |
| Research dataset boundaries | TESTED | versioned timezone-aware half-open train/validation/test windows reject overlap/naive timestamps and have UTC-canonical identity |
| Return-period semantics | TESTED | explicit positive interval, timezone-aware positive strictly regular equity observations; no inferred frequency/annualization |
| Walk-forward fold construction | TESTED | deterministic rolling train/test windows with explicit lengths, step and optional embargo; half-open deterministic fold IDs |
| OOS provenance/results | TESTED | boundary/fold/spec/strategy/features/stream/backtest config/execution costs and deterministic result identity |
| Fixed-strategy OOS evaluation | TESTED | accepts test-window events only and rejects train/out-of-window leakage rather than filtering it |
| Sharpe/Sortino | TESTED | explicit `periods_per_year`; documented sample-SD Sharpe and lower-partial-moment Sortino conventions |
| Fixed-strategy walk-forward reporting | TESTED | compatible ordered fold summaries with arithmetic mean fold return; overlapping test windows are not merged or compounded |
| Research warm-up/fitted-state provenance | TESTED | boundary/fold/spec/strategy/features/source-window/source-stream/serialized-state digests; test leakage rejected |
| Closed-candle warm-state transfer | TESTED | bounded versioned serialization binds strategy/instrument/interval and closed history; malformed/incompatible state fails closed; incomplete source candle excluded |
| Warm OOS evaluation | TESTED | restores compatible closed pre-test history only; preparation-state ID bound to OOS result |
| Validation split/selection | TESTED | deterministic fit/optional-embargo/validation split inside parent train; stable objective/direction-bound tie-breaking |
| Validation backtest evidence | TESTED | validation-window-only real backtest results bind strategy/features/config/normalized stream and derive objective scores |
| Validation search orchestration | TESTED | explicit unique candidates evaluated in deterministic candidate-ID order; duplicate identities/test-window events rejected; stable candidate-set/search identities |
| Selection-bound OOS | TESTED | exact selected candidate/fold/decision required before test evaluation |
| Selected + warm OOS | TESTED | validates selected candidate first, then compatible train-derived warm state; decision/candidate/preparation/OOS IDs jointly bound |
| EMA parameter grid | TESTED | versioned immutable Cartesian grid, positive integer axes, duplicate rejection, canonical order, strict `fast < slow`, stable grid ID and declared-strategy identity check |
| Multi-fold EMA validation-grid search | TESTED | same grid, `SelectionSpec` and objective reused across ordered folds; per-fold validation boundary rejects test evidence; deterministic multi-fold search identity |
| Grid-search-bound selected + warm OOS | TESTED | exact grid/search evidence is bound to selected candidate, train preparation and OOS result; mismatched selection fold/unselected candidate rejected |
| EMA grid selected/warm OOS reporting | TESTED | ordered contiguous fold summaries preserve grid/search/decision/candidate/preparation/result IDs and arithmetic mean fold return; no trade/P&L merge or cross-fold compounding |
| Walk-forward optimization / Monte Carlo | IN_PROGRESS | EMA grid validation/search and traceable OOS reporting are tested; generic optimization, Monte Carlo and distributed orchestration remain pending |
| Generic fitted/model-state execution | NOT_STARTED | current warm path transfers replay closed-candle history for stateless strategy evaluation; no generic mutable strategy/model/feature fitted-state export/import exists |

## Trading, persistence and safety

| Capability | Status | Evidence / notes |
|---|---|---|
| OMS | TESTED | state transitions, fill caps, duplicate-fill idempotency and recovered state |
| Durable order/fill persistence | TESTED | decision linkage, deduplication, persistence and recovery |
| Paper broker / durable paper execution | TESTED | deterministic fills/positions; DB order/fill/audit commit precedes in-memory publication; duplicate/audit/DB failures fail closed |
| Portfolio/P&L | TESTED | realized/unrealized P&L, partial close, reversal and durable rebuild |
| Journal/audit | TESTED | append-only journal and idempotent audit persistence |
| Replay → durable paper integration | TESTED | replay decision reaches transactional durable paper persistence |
| Paper E2E workflow | TESTED | decision → risk → OMS → paper fill → position → reconciliation plus replay→durable-paper |
| Independent risk engine | TESTED | `TradingDecision`-only path, notional gates and operational controls |
| Kill switches / operational modes | TESTED | global/account/strategy/instrument locks plus READ_ONLY/CLOSE_ONLY/HALTED semantics |
| Persistent risk controls | TESTED | migration `0007` establishes singleton operational state; missing/invalid/malformed/unavailable persisted controls fail closed |
| Operational health / persisted escalation | TESTED | unavailable critical health halts; degradation restricts; persistence failure retains restrictive in-memory state; healthy state never auto-relaxes operator controls |
| Live-trading gate policy | TESTED | deny by default; requires explicit approval, authorization, broker auth, reconciliation, strategy/capital approval, healthy systems and normal unlocked controls |
| Reconciliation / restart recovery | TESTED | position match/mismatch plus OMS/fill/paper-position/risk-control recovery from PostgreSQL |
| Failure/security validation | IN_PROGRESS | Bandit green; rollback, DB-unavailable paths, restart, transient provider failure, master-sync conflict, bounded retrieval, response uniqueness, checkpoint integrity/atomicity and control corruption covered; broader fault matrix pending |
| Real broker order adapter | NOT_STARTED | no order-submission API exists |
| Real execution/reconciliation | NOT_STARTED | paper path only |
| Controlled live release | NOT_STARTED | live remains disabled and is not approved |

## Later subsystems

| Capability | Status | Evidence / notes |
|---|---|---|
| Options engine | NOT_STARTED | later phase |
| ML subsystem | NOT_STARTED | later phase |
| Next.js frontend | NOT_STARTED | later phase |

## Validation evidence

A green cumulative `main` CI run completed for code commit `17e878e8159168cfa273b21149ebea5693d9d13b` in GitHub Actions run `36712796063`.

That workflow passed:

- dependency installation
- Ruff
- strict MyPy
- PostgreSQL migrations through `0007`
- full Pytest suite including PostgreSQL and Redis integration tests
- Bandit
- Alembic downgrade-to-base and reapply-to-head
- Docker image build
- runtime package smoke imports

Newly validated in this coding cycle:

- deterministic versioned EMA crossover parameter-grid materialization with strict Cartesian semantics and stable grid identity;
- validation-only grid search that verifies generated backtester strategy identity against each declared grid candidate;
- multi-fold grid search that reuses one declared grid/selection specification/objective across ordered walk-forward folds and rejects test-window contamination through the existing validation boundary;
- grid/search provenance carried into selected+warm OOS so the test result remains traceable to exact pre-test search evidence;
- grid-selected warm OOS reporting that preserves per-fold search, selection, candidate and preparation identities while deliberately avoiding synthetic cross-fold trade/P&L aggregation or return compounding.

Previously validated replay/backtest restartability, data/provider contracts, paper execution, persistent controls, risk gates and failure-hardening behavior remain green in the cumulative run.

## Important validation boundaries

- Provider historical HTTP and master-retrieval tests are mocked. They do **not** prove current credentials, entitlements, provider availability or a successful live CSV transfer.
- Canonical Upstox/Dhan services use PostgreSQL plus mocked provider HTTP, not real provider accounts.
- The real Dhan compact-master octet-stream transfer remains unverified in this environment.
- Provider-master synchronization never auto-creates or symbol-matches canonical instruments.
- Replay/backtest checkpointing is local deterministic persistence, not distributed job orchestration or an exactly-once guarantee for arbitrary external side effects.
- Interrupted checkpoint-write coverage is deliberate fault injection around atomic replacement, not exhaustive filesystem/power-loss validation.
- The warm-state path transfers replay-pipeline closed-candle history only. It does not serialize mutable strategy internals, fitted model parameters, feature-engine state, optimizer state or arbitrary external state.
- Pending/incomplete training candles are intentionally not transferred into test execution.
- The parameter-grid implementation is deliberately EMA-crossover-specific. It is not represented as a generic optimizer framework.
- `EmaCrossoverParameterGrid.from_axes` materializes the complete Cartesian product and rejects any invalid `fast >= slow` pair rather than silently dropping declared combinations.
- Multi-fold grid search currently receives explicit validation-event inputs per fold. Automatic dataset partition/slicing orchestration is not implemented.
- Candidate ranking uses validation results only. Test-fold results never participate in candidate selection or tuning.
- Different folds may select different strategy/configuration identities; the EMA grid OOS report therefore preserves those identities per fold rather than pretending there is one common selected strategy.
- Grid OOS reporting is fold-level evidence. It does not sum trades/P&L or compound returns across folds, because test windows may overlap when walk-forward step is shorter than test length.
- Sharpe/Sortino conventions are repository-specific documented choices, not uniquely correct definitions for every research setting.
- Walk-forward construction is rolling fixed-length; expanding-window or purged-cross-validation semantics are not claimed.
- Migration `0007` downgrade intentionally does not delete operator-modified persisted operational state; owning table removal occurs at migration `0005`.
- CI validates repository/container behavior, not a deployed production environment.
- Backtest/metric outputs are deterministic research results, not profitability claims.
- No real broker order endpoint is implemented or called. Live trading remains disabled and unapproved.

## Highest-priority work

1. Add automatic fold dataset slicing/orchestration only if it preserves explicit half-open boundaries and fails closed on missing, duplicate or out-of-window evidence rather than silently filtering leakage.
2. Define generic fitted/model/feature-state export/import only when a concrete stateful research component requires it; do not misrepresent closed-candle warm-up as arbitrary fitted-state restoration.
3. Define Monte Carlo semantics before implementation: sampling unit, replacement policy, deterministic seed, path count and preserved temporal/dependency relationships.
4. Continue persistence/network/provider failure injection only where a distinct fail-closed invariant remains untested.
5. Extend versioned feature outputs only when the next feature has an explicit event-time/reproducibility boundary.
6. Validate a real Dhan compact-master transfer in a compatible environment and authenticated provider smoke tests only with securely supplied runtime credentials.
7. Keep broker order submission out of scope until every live gate is integrated, validated and explicitly approved.

## Blockers

No blocker for continued local research/paper development. Real authenticated historical-provider validation requires user-supplied credentials/entitlements through secure runtime configuration. Real Dhan master transfer validation requires an environment that can successfully consume the provider's octet-stream response. Live trading remains deliberately unavailable and no broker order execution has been introduced.

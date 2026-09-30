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
| Implementation tracking | IN_PROGRESS | This file is maintained during coding cycles |
| Current phase tracking | IN_PROGRESS | `plans/CURRENT_PHASE.md` |
| Next task tracking | IN_PROGRESS | `plans/NEXT_TASKS.md` |

## Platform capabilities

| Capability | Status | Evidence / notes |
|---|---|---|
| Python/FastAPI foundation | TESTED | Ruff, strict MyPy, Pytest, Bandit and Docker pass on `main` |
| Typed configuration | TESTED | live trading defaults off; enabling outside LIVE is rejected |
| PostgreSQL/SQLAlchemy/Alembic | TESTED | migrations 0001-0007 apply, downgrade to base and reapply against PostgreSQL |
| Redis | TESTED | real Redis readiness integration coverage in CI |
| Structured logging/request correlation | TESTED | request-ID generation/preservation covered |
| Health/readiness | TESTED | liveness and fail-closed database/Redis readiness covered |
| Docker runtime | TESTED | image builds after runtime-only install and imports app/provider modules |
| CI | TESTED | cumulative `main` run `36710434256` completed successfully |
| Instrument master | TESTED | canonical instrument/provider identifier schema and migration validation |
| Provider identifier classification metadata | TESTED | migration 0006 adds nullable provider exchange-segment/instrument-type/expiry-code fields without breaking existing identifiers |
| Provider identifier resolver | TESTED | point-in-time/full-range references resolve external ID plus provider metadata; missing, overlapping and rollover-crossing mappings fail closed |
| Dhan compact-master parser | TESTED | documented compact fields are parsed with strict exchange/segment/instrument/expiry validation and duplicate-security-ID conflict detection |
| Dhan master synchronizer | TESTED | synchronization is scoped to incoming security IDs, updates only existing Dhan links, fills missing metadata only, pre-validates all conflicts before mutation and never creates canonical instruments by symbol guess |
| Dhan compact-master retrieval boundary | TESTED | exact official compact URL is pinned, redirects disabled, timeout and byte cap enforced, response streamed, UTF-8/BOM handled; HTTP behavior validated with `httpx.MockTransport` |
| Dhan transactional master refresh | TESTED | fetch/parse completes before opening the PostgreSQL transaction; conflict-safe synchronization commits atomically and persistence is verified from a fresh session using mocked HTTP + real PostgreSQL |
| Real Dhan compact-master transfer | IMPLEMENTED_UNVERIFIED | retrieval code exists, but no successful live octet-stream transfer has been validated in this environment |
| Recorded market events | TESTED | provider-neutral recorded trade envelope, timestamps, ordering, dedupe/conflict checks |
| Recorded JSONL ingestion | TESTED | Decimal/timestamp round-trip, normalization and malformed-input rejection |
| Provider-neutral historical source | TESTED | local JSONL source, filtering and multi-source normalization |
| Provider historical OHLC model | TESTED | timezone/provenance/positive-price/OHLC coherence/volume/OI invariants covered |
| Provider response uniqueness | TESTED | Upstox and Dhan responses with duplicate candle timestamps are rejected before normalization/research |
| Historical provider normalization | TESTED | provider OHLCV bars convert to canonical closed candles without inventing trades |
| Upstox historical read-only client | TESTED | V3 request shape represented; exact URL/auth/header/response behavior covered with `httpx.MockTransport` only |
| Canonical Upstox historical service | TESTED | canonical instrument→full-range provider ID→read-only client path tested; rollover-crossing range rejected before HTTP |
| Dhan historical read-only client | TESTED | v2 daily/intraday request/response shapes represented; daily expiry code restricted to documented 0/1/2; covered with `httpx.MockTransport` only |
| Canonical Dhan daily cash service | TESTED | canonical NSE/BSE cash instrument→full-range Dhan security ID→explicit cash classification→daily client; rollover fails before HTTP |
| Canonical Dhan daily derivatives | TESTED | FUTIDX/FUTSTK/OPTIDX/OPTSTK require explicit persisted NSE/BSE F&O segment, instrument type and expiry code; missing/mismatched metadata fails before HTTP |
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
| Versioned regime feature output | TESTED | parameter-specific `v1` feature identity canonicalizes Decimal thresholds and carries canonical instrument plus closed-candle `as_of` provenance |
| Broader feature-output versioning | IN_PROGRESS | regime is versioned; extend only as additional derived features get explicit reproducibility/event-time boundaries |
| Strategy identity | TESTED | `StrategyEvaluator` requires stable `strategy_id`; EMA crossover uses immutable parameter-specific `v1` IDs |
| Strategy registry/lifecycle | TESTED | immutable registration by strategy ID, fresh factory resolution, explicit retirement, historical retired-version resolution and factory identity/history revalidation |
| Strategy framework | IN_PROGRESS | identity and registry/lifecycle are tested; additional strategies remain pending |
| Decision engine | TESTED | explicit TradingDecision contract and fail-closed invalid-price/no-direction behavior |
| Scanner | NOT_STARTED | later phase |
| Replay | TESTED | normalized deterministic event stream and event→closed-candle→strategy→decision pipeline |
| Replay checkpoint/resume | TESTED | versioned JSON checkpoint binds cursor/event count to SHA-256 digest of normalized stream; changed datasets/counts/malformed state fail closed |
| Replay checkpoint file persistence | TESTED | bounded UTF-8 local file store uses secure temp creation, file+directory fsync and atomic replacement; fresh-process-style load/restore covered in CI |
| Replay → durable paper integration | TESTED | replay decision reaches transactional durable paper persistence |
| Event-driven backtester | TESTED | production-style replay/strategy/decision/risk/paper contracts, explicit fees/slippage, risk rejection and future-event isolation |
| Backtest durable continuation | TESTED | versioned full-state checkpoint persists replay cursor, closed/open candle state, position/P&L, trades, equity, fees/drawdown and rejection count; fresh backtester resume after a simulated fill exactly matches uninterrupted result |
| Backtest checkpoint configuration binding | TESTED | checkpoint binds strategy type/ID, interval, requested quantity, starting capital, execution assumptions, risk limits, operational mode and active risk locks; stream/config changes fail closed |
| Backtest checkpoint internal integrity | TESTED | schema-valid state is cross-checked for trade/P&L/position/fee/drawdown consistency plus processed replay-prefix pipeline/equity correspondence |
| Backtest restore atomicity | TESTED | restore validates candidate replay/pipeline/economic state before swapping session state; failed restore leaves an existing session unchanged |
| Backtest checkpoint file persistence | TESTED | bounded UTF-8 JSON state uses secure temporary file creation, fsync and atomic replace; injected replace failure preserves the last good file and cleans temporary state |
| Backtest core analytics | TESTED | event-time equity curve, total return, max drawdown, trade counts, realized wins/losses, gross P/L and profit factor |
| Research dataset boundaries | TESTED | versioned timezone-aware half-open train/validation/test windows reject overlap/naive timestamps, allow explicit gaps and use a UTC-canonical deterministic boundary identity |
| Return-period semantics | TESTED | explicit positive interval required; equity observations must be timezone-aware, positive, strictly ordered and exactly regular; simple returns are computed without inferring frequency or annualization |
| Walk-forward fold construction | TESTED | deterministic rolling train/test windows use explicit lengths, step and optional embargo; folds are half-open, have UTC-canonical deterministic fold IDs, and no truncated final fold is emitted |
| OOS evaluation/provenance | TESTED | versioned provenance/result envelopes bind boundary, fold/spec, strategy, ordered feature IDs, normalized stream digest, backtest config digest, execution costs and full deterministic backtest result identity |
| Fixed-strategy OOS fold evaluation | TESTED | cold-start evaluator accepts only events inside the half-open test window, rejects train/out-of-window leakage instead of filtering it, runs a fixed strategy/configuration and emits deterministic OOS provenance/result envelopes |
| Research warm-up/fitted-state provenance | TESTED | versioned state provenance binds boundary/fold/spec, strategy/features, exact train or trailing warm-up source window, normalized source-stream digest and serialized-state digest; test-window leakage is rejected |
| Closed-candle warm-state transfer | TESTED | versioned bounded serialization binds strategy, instrument, interval and closed-candle history; malformed/tampered payloads and incompatible/freshness violations fail closed; incomplete source-window candles are deliberately excluded from transfer |
| Warm-state OOS evaluation | TESTED | test-only OOS execution can restore compatible closed-candle warm-up history only when boundary/fold/spec/strategy/features/instrument/interval match and every transferred candle ends before the test window; result identity binds the preparation-state ID to the OOS result |
| Validation split/selection contract | TESTED | deterministic fit/optional-embargo/validation split stays wholly inside the parent train window and preserves the test window; candidate evidence is bound to fold, objective and direction with deterministic tie-breaking |
| Validation backtest evidence | TESTED | validation evaluator accepts only validation-window events, binds strategy/features/backtest configuration and normalized stream to a deterministic result identity, and derives objective scores from the real backtest result |
| Selection-bound OOS evaluation | TESTED | selected OOS execution requires the exact parent fold/selection fold/decision and candidate identity chosen from validation evidence before evaluating test-window events; result identity binds the selection decision to the OOS result |
| Selected + warm OOS evaluation | TESTED | one OOS boundary now requires the exact validation-selected candidate and a compatible train-derived warm preparation before test execution; immutable result identity jointly binds selection decision, candidate, preparation-state and OOS result IDs |
| Sharpe/Sortino/annualized metrics | TESTED | requires explicit `periods_per_year`; Sharpe uses arithmetic mean excess return over sample standard deviation; Sortino uses arithmetic mean above target over population lower-partial-moment downside deviation; zero denominator returns `None` |
| Walk-forward aggregate reporting | TESTED | ordered contiguous fold results require compatible boundary/spec/strategy/features/config/execution assumptions; report identity is UTC-canonical and immutable; summaries remain fold-level and use arithmetic mean fold return without summing/compounding potentially overlapping folds |
| Walk-forward optimization/Monte Carlo | NOT_STARTED | parameter search/orchestration and Monte Carlo remain pending; build only on explicit provenance and leakage protections |
| Generic fitted/model-state execution | NOT_STARTED | the tested warm-state path transfers replay-pipeline closed-candle history for stateless strategy evaluation; no generic mutable strategy/model/feature fitted-state export-import or restoration contract exists |
| OMS | TESTED | state transitions, fill caps, duplicate-fill idempotency and recovered state |
| Durable order/fill persistence | TESTED | decision linkage, deduplication, persistence and recovery |
| Paper broker | TESTED | deterministic market fill and position updates |
| Durable paper execution | TESTED | order/fill/audit commit precedes in-memory publication; duplicate/audit/DB-unavailable failures fail closed |
| Portfolio/P&L | TESTED | realized/unrealized P&L, partial close, reversal and durable rebuild |
| Journal/audit | TESTED | append-only journal behavior and idempotent AuditEvent persistence |
| Independent risk engine | TESTED | TradingDecision-only path, notional gates and operational controls |
| Kill switches | TESTED | global/account/strategy/instrument locks and READ_ONLY/CLOSE_ONLY/HALTED semantics |
| Persistent risk controls | TESTED | migration `0007` establishes the singleton operational-state initialization invariant; all load/mutation paths require it; missing singleton, invalid mode/scope, malformed lock keys and database unavailability fail closed |
| Operational health gate | TESTED | missing/critical-unavailable health halts; degraded/noncritical unavailable forces READ_ONLY |
| Persisted health escalation | TESTED | health-driven restriction persists; persistence failure retains restrictive in-memory mode; healthy state never auto-relaxes operator controls |
| Live-trading gate policy | TESTED | deny-by-default policy requires explicit approval, authorization, broker auth, reconciliation, strategy/capital approval, healthy subsystems and normal unlocked controls |
| Reconciliation | TESTED | position quantity/average-price match/mismatch behavior |
| Restart recovery | TESTED | OMS state, processed fills, paper position and risk controls reconstruct from PostgreSQL; missing/corrupt/unavailable persisted operational-control state fails closed |
| Real broker order adapter | NOT_STARTED | no order-submission API exists |
| Real execution/reconciliation | NOT_STARTED | paper path only |
| Options engine | NOT_STARTED | later phase |
| ML subsystem | NOT_STARTED | later phase |
| Next.js frontend | NOT_STARTED | later phase |
| Paper E2E workflow | TESTED | decision → risk → OMS → paper fill → position → reconciliation plus replay→durable-paper |
| Failure/security validation | IN_PROGRESS | Bandit green; rollback, DB-unavailable execution/control recovery, restart, transient provider failure, master-sync conflict safety, bounded master retrieval, provider-response uniqueness, replay/backtest checkpoint integrity/atomicity, persisted control corruption and health-escalation cases covered; broader fault matrix pending |
| Controlled live release | NOT_STARTED | live remains disabled and is not approved |

## Validation evidence

A green cumulative `main` CI run completed for commit `a8527d02c6791ffdf52f128e1b854648f6685d7b` in GitHub Actions run `36710434256`.

The run passed in one workflow:

- dependency installation
- Ruff
- strict MyPy
- PostgreSQL migrations through `0007`
- full Pytest suite including PostgreSQL and Redis integration tests
- Bandit
- Alembic downgrade-to-base and reapply-to-head
- Docker image build
- runtime package smoke imports

Validated additions in the current cumulative scope include:

- schema-valid backtest checkpoint cross-field integrity checks plus atomic failed-restore behavior and interrupted-replace preservation
- versioned parameter-specific regime feature identity with instrument/event-time provenance
- versioned research dataset boundaries, explicit regular return periods and deterministic rolling walk-forward folds with deterministic fold identity
- versioned OOS provenance/result identities binding dataset boundary, fold/spec, strategy ID, ordered feature IDs, normalized stream, backtest configuration and explicit execution costs
- explicit sample-standard-deviation Sharpe and population lower-partial-moment Sortino with mandatory explicit annualization metadata
- fixed-strategy cold-start OOS fold evaluation that rejects accidental train/out-of-window event leakage and produces deterministic provenance/result IDs
- fold-level immutable walk-forward reports with compatibility/order checks and UTC-canonical report identity; overlapping test windows are not compounded or summed into a synthetic portfolio path
- explicit warm-up/fitted-state provenance with source-window, normalized-stream and serialized-state digests
- deterministic bounded closed-candle warm-state serialization/restore with strategy/instrument/interval binding and deliberate exclusion of an incomplete source-window candle
- warm OOS execution that imports only closed pre-test candle history, rejects provenance/configuration/window mismatches and binds the preparation-state identity to the OOS result
- fit/embargo/validation splitting inside the parent train window, validation-only backtest evidence, objective-bound candidate scores and deterministic selection
- selected OOS evaluation that rejects a backtester/configuration whose candidate identity was not selected from the exact validation fold
- combined selected+warm OOS evaluation that rejects candidate/test-window mismatches before execution and binds decision/candidate/preparation/OOS identities in one result
- migration-backed persistent control initialization plus fail-closed missing state, invalid mode/scope, malformed lock-key and database-unavailable load/mutation coverage
- previously validated full-state checkpoint/resume, immutable strategy registry, provider classification/master ingestion, deterministic replay, historical normalization and trading-safety capabilities remain green in the cumulative run

## Important validation boundaries

- Provider historical HTTP and master-retrieval tests are mocked. They do **not** prove current credentials, entitlements, provider availability, or a successful live CSV transfer.
- The official Dhan compact endpoint is documented as `https://images.dhan.co/api-data/api-scrip-master.csv`; the available external web fetcher could not consume the provider's octet-stream response, so live-transfer success is not claimed.
- Canonical Upstox/Dhan services are integration-tested against PostgreSQL plus mocked HTTP, not real provider accounts.
- Provider-master synchronization never auto-creates or symbol-matches canonical instruments; only pre-existing Dhan security-ID links are enriched.
- Replay-only checkpoint files persist cursor/stream identity; full backtest checkpoints separately persist deterministic research economic state.
- Backtest checkpointing is local file persistence, not a distributed scheduler/job runner or production research service.
- Backtest integrity checks reconstruct deterministic local simulator state from persisted trades/replay prefix; they are not a cryptographic authenticity mechanism and do not imply exactly-once guarantees for arbitrary external side effects.
- Interrupted-write coverage is deliberate fault injection around atomic replace, not a claim of exhaustive power-loss/filesystem-crash validation.
- Versioned regime output is the first concrete derived-feature contract; no generic feature registry or universal schema is claimed.
- The tested warm-state path transfers replay-pipeline closed-candle history only. It does not serialize mutable strategy internals, fitted model parameters, feature-engine internal state, optimizer state or arbitrary external state.
- Pending/incomplete training candles are intentionally not transferred across the train→test boundary, preventing the first test event from closing a pre-test candle and emitting a contaminated OOS decision.
- Validation selection currently operates on explicitly supplied candidate backtest configurations and two repository-defined objectives; no automatic parameter grid/search engine or statistical significance claim is implemented.
- Combined selected+warm OOS first validates the candidate chosen from validation, then applies train-derived closed-candle history; the preparation state does not alter which candidate validation selected.
- Walk-forward aggregate reports are fold-level summaries. Because generated folds may have overlapping test windows when `step < test_length`, the report deliberately does not sum trades/P&L or compound fold returns into a single path.
- Sharpe/Sortino use the explicitly documented repository conventions only; no claim is made that those conventions are uniquely correct for every research use case.
- Walk-forward folds are rolling fixed-length construction; expanding-window or purged-cross-validation semantics are not claimed.
- Migration `0007` is a data-initialization migration; its downgrade intentionally does not delete persisted operational state because deleting an operator-modified safety mode would be an unsafe data-loss side effect. Downgrade-to-base still removes the owning table at migration `0005`.
- No real broker order endpoint is implemented or called.
- CI validates repository/container behavior, not a deployed environment.
- Backtest results and risk-adjusted metrics are deterministic research outputs, not profitability claims.
- Live trading remains disabled and unapproved.

## Highest-priority work

1. Add deterministic parameter-grid/search orchestration that emits validation evidence and selection decisions only; test-fold outcomes must never participate in candidate ranking.
2. Define generic fitted/model/feature-state export-import only when a stateful research component requires it; do not misrepresent closed-candle warm-up as arbitrary fitted-state restoration.
3. Extend selected/warm OOS aggregate reporting only if every fold retains its selection-decision and preparation-state identities and overlapping test folds are not synthesized into one path.
4. Continue persistence/network/provider failure injection only where a distinct fail-closed invariant remains untested; avoid redundant synthetic cases now that persisted-control missing/corrupt/unavailable paths are covered.
5. Extend versioned feature-output contracts to the next derived feature only when its reproducibility/event-time boundary is explicit.
6. Validate a real Dhan compact-master transfer in an environment that supports the octet-stream endpoint, then record retrieval metadata/freshness without auto-linking instruments.
7. Keep all broker order submission out of scope until every live gate is integrated, validated and explicitly approved.

## Blockers

No blocker for continued research/paper development. Real authenticated historical-provider validation requires user-supplied credentials/entitlements through secure runtime configuration. A real Dhan master transfer could not be validated through the available web retrieval path because it does not accept the endpoint's octet-stream content. Live trading remains deliberately unavailable and no broker order execution has been introduced.

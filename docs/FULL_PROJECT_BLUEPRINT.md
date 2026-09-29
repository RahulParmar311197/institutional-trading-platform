# Institutional Trading Platform — Full Project Blueprint

This document is the expanded execution blueprint discussed during project design. `docs/MASTER_BLUEPRINT.md` remains the compact architectural contract; this file is the detailed build map for humans and coding agents.

## 1. Product objective

Build an India-first institutional-style quantitative trading platform covering the complete lifecycle:

Discover → Research → Analyze → Scan → Design Strategy → Replay → Backtest → Validate → Paper Trade → Shadow Trade → Risk Approve → Controlled Live Trade → Monitor → Reconcile → Journal → Improve.

Initial target:

- India / NSE-first architecture, extensible to BSE and future venues
- NIFTY, BANKNIFTY and selected liquid NSE equities
- Equity, futures and options
- Intraday and swing/systematic workflows
- Upstox and Dhan broker adapters after safe paper validation
- Multi-timeframe market analysis
- Deterministic technical analysis and SMC/ICT
- Options/OI/IV/Greeks intelligence
- Research, replay, event-driven backtesting and walk-forward validation
- Paper, shadow and controlled live execution
- Independent portfolio/risk controls
- AI/ML as advisory/scoring infrastructure, never as an unrestricted broker controller

## 2. Fundamental execution architecture

Never build:

`LLM → BUY/SELL → Broker`

Required path:

`Market Data → Data Validation → Feature Engine → Alpha/Strategy → Decision Engine → Portfolio Construction → Independent Risk → Execution Policy → OMS → EMS → Broker Adapter → Exchange/Broker → Fill Reconciliation → Portfolio/P&L/Journal`

The strategy proposes. Portfolio construction sizes/allocates. Risk can approve, resize, reject or halt. OMS owns durable order state. Execution decides how approved intent is expressed. Broker adapters translate canonical orders into provider APIs. Reconciliation validates economic truth.

## 3. Institutional system map

### Data plane

Exchange/Broker/Data Provider → ingestion → immutable/raw data → normalization → point-in-time canonical data → features → strategy/ML consumers.

### Trading plane

Signals → decisions → target portfolio → risk → OMS/EMS → broker/exchange → fills → positions/accounting → reconciliation.

### Control plane

Strategy activation, capital allocation, risk limits, model promotion, feature flags, trading sessions, broker accounts, maintenance mode, kill switches and user permissions.

### Research plane

Datasets → feature definitions → experiments → backtests → OOS/walk-forward/stress → candidate strategy/model → registry → paper/shadow promotion.

### Operations plane

Metrics, logs, traces, health, surveillance, incidents, audit, backups and runbooks.

## 4. Recommended stack

### Backend

- Python 3.12+
- FastAPI
- Pydantic v2
- SQLAlchemy 2
- Alembic
- AsyncIO
- HTTPX
- WebSockets

### Quant

- NumPy
- Polars
- Pandas only where ecosystem compatibility requires it
- SciPy
- statsmodels
- scikit-learn
- XGBoost / LightGBM when ML phase begins
- Numba only after profiling demonstrates need

### Storage

- PostgreSQL as durable transactional source of truth
- TimescaleDB where time-series query patterns justify it
- Redis for cache/ephemeral coordination/fan-out/rate limits, not sole trading truth
- Parquet + S3-compatible object storage for large historical/research datasets

### Frontend

- Next.js
- React
- TypeScript
- TradingView Lightweight Charts
- TanStack Query
- Zustand
- WebSocket client

### Infrastructure

- Docker / Docker Compose
- GitHub Actions
- Linux
- reverse proxy when deployment requires it
- OpenTelemetry
- Prometheus
- Grafana

### Quality

- Pytest
- Ruff
- MyPy
- Bandit
- dependency/secret scanning
- Vitest
- Playwright

Start with a modular monolith plus workers. Do not introduce Kafka, Kubernetes or dozens of services until measured requirements justify them.

## 5. Target repository architecture

```text
institutional-trading-platform/
├── AGENTS.md
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
├── CHANGELOG.md
├── .gitignore
├── .editorconfig
├── .env.example
├── Makefile
├── pyproject.toml
├── package.json
├── docker-compose.yml
├── docs/
│   ├── MASTER_BLUEPRINT.md
│   ├── FULL_PROJECT_BLUEPRINT.md
│   ├── IMPLEMENTATION_STATUS.md
│   ├── ROADMAP.md
│   ├── ARCHITECTURE.md
│   ├── DEFINITION_OF_DONE.md
│   ├── SECURITY_MODEL.md
│   ├── LIVE_TRADING_GATES.md
│   ├── TESTING_STRATEGY.md
│   ├── DATA_MODEL.md
│   ├── API_DESIGN.md
│   ├── BROKER_INTEGRATION.md
│   ├── RISK_MODEL.md
│   ├── SMC_ICT_SPEC.md
│   ├── BACKTEST_SPEC.md
│   ├── ML_SPEC.md
│   ├── DEPLOYMENT.md
│   └── runbooks/
├── plans/
│   ├── CURRENT_PHASE.md
│   ├── NEXT_TASKS.md
│   ├── BLOCKERS.md
│   └── DECISIONS.md
├── apps/
│   ├── api/
│   ├── web/
│   ├── worker/
│   ├── scheduler/
│   └── research/
├── packages/
│   ├── domain/
│   ├── config/
│   ├── database/
│   ├── market_data/
│   ├── instrument_master/
│   ├── data_quality/
│   ├── candle_engine/
│   ├── feature_store/
│   ├── indicators/
│   ├── price_action/
│   ├── smc_ict/
│   ├── orderflow/
│   ├── market_profile/
│   ├── options/
│   ├── regime/
│   ├── factors/
│   ├── alpha/
│   ├── strategies/
│   ├── decision_engine/
│   ├── portfolio/
│   ├── risk/
│   ├── oms/
│   ├── ems/
│   ├── execution/
│   ├── brokers/
│   ├── backtesting/
│   ├── replay/
│   ├── paper_trading/
│   ├── machine_learning/
│   ├── surveillance/
│   ├── reconciliation/
│   ├── accounting/
│   ├── journal/
│   ├── notifications/
│   ├── audit/
│   └── observability/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── property/
│   ├── regression/
│   ├── backtest/
│   ├── performance/
│   ├── failure/
│   ├── security/
│   └── e2e/
├── infra/
│   ├── docker/
│   ├── monitoring/
│   ├── deployment/
│   └── migrations/
├── research/
│   ├── notebooks/
│   ├── experiments/
│   └── datasets/
└── .github/
    ├── workflows/
    ├── ISSUE_TEMPLATE/
    └── pull_request_template.md
```

Directories should be created as implementation requires them. Do not generate hundreds of empty placeholder modules merely to match this tree.

## 6. Canonical domain model

### Reference/market

Exchange, Instrument, InstrumentIdentifier, TradingSession, TradingCalendar, Tick, Trade, Quote, OrderBookSnapshot, Candle, FutureContract, OptionContract, OptionChain, OptionQuote, Greeks, CorporateAction, MarketEvent and DataQualityEvent.

### Trading

Signal, AlphaSignal, StrategyDecision, PortfolioDecision, RiskDecision, OrderIntent, ExecutionInstruction, BrokerOrder, OrderEvent, Fill, Position, Holding, TradeRecord, Portfolio, Account, FundsSnapshot and PnLSnapshot.

### Research

DatasetVersion, UniverseVersion, FeatureDefinition, FeatureSnapshot, StrategyVersion, Experiment, BacktestRun, ModelVersion and Prediction.

### Operations

RiskLimit, KillSwitch, ReconciliationRun, AuditEvent, Incident, SystemHealth and Deployment/Configuration version.

Use `Decimal` or equivalent exact semantics for monetary/accounting values where binary floating-point error is unacceptable. Store timestamps in UTC internally while preserving exchange/source timestamps and timezone/session semantics.

## 7. Instrument master

Maintain a canonical security master containing:

- internal instrument ID
- exchange/segment
- symbol/trading symbol
- ISIN where applicable
- exchange/provider/broker mappings
- underlying
- expiry
- strike
- option type
- lot size
- tick size
- price limits
- contract multiplier
- trading status
- effective-from/to metadata

Strategies use internal IDs, never raw Upstox/Dhan tokens.

## 8. Market-data platform

Support:

- historical OHLCV
- live trades
- live quotes
- L1
- L2/depth where source supports it
- futures
- option chains
- OI
- IV/Greeks
- instrument masters
- corporate actions
- exchange calendars/sessions
- market/event feeds when licensed/available

Pipeline:

`Provider → Connector → Raw Event → Schema validation → Timestamp/sequence validation → Deduplication → Ordering → Normalization → Quality checks → Canonical Event → Storage + Distribution`

Capture exchange timestamp, provider timestamp, ingestion timestamp, sequence number, instrument ID, source and quality status where available.

## 9. Data-quality engine

Detect:

- missing data
- duplicates
- out-of-order events
- timestamp drift
- stale quotes
- invalid/negative prices or volumes
- extreme/unexplained jumps
- session violations
- candle gaps
- instrument mapping mismatch
- sequence gaps
- crossed bid/ask
- provider outage

Quality states: GOOD, DEGRADED, STALE, INVALID, MISSING.

Trading logic must be able to return `NO_TRADE: DATA_QUALITY_FAILURE` or trigger a risk/operational lock.

## 10. Storage layers

Separate conceptual layers:

RAW → NORMALIZED → DERIVED → FEATURES → SIGNALS/DECISIONS → ORDERS/FILLS → ACCOUNTING/AUDIT.

Raw source data should be immutable where practical. Derived values must be reproducible from versioned inputs and algorithms.

## 11. Candle engine

Native targets:

1m, 3m, 5m, 15m, 30m, 1h, 4h, 1d, 1w.

Generate higher timeframes only from eligible closed data. Explicitly handle NSE session boundaries, holidays and incomplete bars. Prevent look-ahead.

Example multi-timeframe workflow:

4H directional regime → 1H structure → 15m setup → 5m confirmation → 1m execution context.

## 12. Technical indicator engine

Implement deterministic, versioned calculations for SMA, EMA, WMA, RSI, MACD, ATR, ADX, Bollinger Bands, Keltner Channels, ROC, Stochastic, CCI, VWAP, Anchored VWAP, Supertrend, OBV, MFI, RVOL, volume averages, pivot points, Donchian channels, historical volatility and realized volatility.

Every indicator defines inputs, parameters, warm-up requirements, missing-data behavior, outputs and algorithm version. Validate against trusted reference calculations.

## 13. Price-action engine

Detect swings, trend structure, support/resistance, breakouts, retests, ranges, compression/expansion, gaps, impulse/pullback, inside/outside bars and session highs/lows. Thresholds are explicit/configurable; no subjective chart interpretation in execution logic.

## 14. SMC / ICT engine

First-class deterministic package covering:

- BOS
- CHoCH
- MSS
- displacement
- FVG / IFVG
- order block
- mitigation block
- breaker block
- equal highs/lows
- BSL / SSL
- liquidity sweep / grab
- PDH / PDL / PWH / PWL
- session highs/lows
- premium / discount / equilibrium
- OTE
- consequent encroachment
- configurable kill zones/sessions

Each structure records type, instrument, timeframe, time/price bounds, direction, strength/quality measures, invalidation, mitigation state, source candles and algorithm version.

No future candles and no repainting historical signals as if they existed in real time.

## 15. Order-flow / microstructure

Only when data quality permits:

- bid/ask spread
- depth imbalance
- order-book imbalance
- trade imbalance
- microprice
- aggressor estimation
- liquidity score
- depth concentration
- volume delta / cumulative delta
- absorption proxies
- large-trade detection
- short-horizon realized volatility

Disable features when source data is insufficient. Never invent L2/order-flow from candles.

## 16. Market profile

Volume Profile, POC, VAH, VAL, session/composite profiles, VWAP bands, opening range and initial balance. Treat primarily as context until individual predictive value is validated.

## 17. Regime engine

Classify BULL_TREND, BEAR_TREND, RANGE, BREAKOUT, TRANSITION; HIGH/NORMAL/LOW_VOL; HIGH/LOW_LIQUIDITY; EVENT_RISK; EXPIRY; OPENING; CLOSING.

Return regime, confidence/score where meaningful, evidence/features, timestamp and version. Start deterministic before ML.

## 18. Factor engine

For cross-sectional strategies support validated factors such as momentum, value/quality when point-in-time fundamentals exist, volatility, liquidity, size, relative strength, beta, sector momentum, breadth and mean reversion. Maintain point-in-time universes to avoid survivorship bias.

## 19. Alpha framework

Strategies produce alpha/signals, not broker orders. Standard fields include instrument, timestamp, direction, horizon, strength, expected return/risk where modeled, confidence where calibrated, entry region, invalidation, features/evidence, explanation and strategy version.

## 20. Strategy framework

A strategy declares metadata, required data/features, universe, evaluation, entry rules, exit rules, invalidation and explanation.

Initial research library:

1. Trend continuation
2. HTF trend + pullback
3. VWAP continuation
4. Opening-range breakout
5. Liquidity-sweep reversal
6. SMC FVG continuation
7. Order-block retest
8. Momentum breakout
9. Range mean reversion
10. Relative strength
11. Volatility breakout
12. Options momentum/volatility research

Do not launch all strategies live simultaneously.

## 21. Decision engine

Inputs can include technical signals, SMC/ICT, order flow, regime, volume, options, factors, ML scores, data quality, positions and strategy health.

Outputs: LONG, SHORT, EXIT, REDUCE, HOLD, NO_TRADE.

Decision records should include evidence/rejection reasons, snapshot ID, version, entry/invalidation/targets when strategy-defined, and calibrated—not arbitrary—confidence.

## 22. Portfolio construction

`Alpha Signals → Expected Return/Risk → Correlation → Current Portfolio → Constraints → Target Positions`

Support position sizing, volatility targeting, risk budgets, strategy allocation, instrument/sector limits, gross/net exposure, beta/correlation constraints and hedging.

Later research: mean-variance, risk parity, minimum variance, maximum diversification and CVaR. Optimizers require robust constraints and OOS validation.

## 23. Options intelligence

Per option: LTP, bid, ask, spread, volume, OI, change OI, IV, delta, gamma, theta, vega, rho.

Chain analytics: PCR, OI/change-OI concentration, max pain where useful, expected move, IV rank/percentile, skew, smile, term structure and liquidity.

Implement and validate Black-Scholes, Black-76 where appropriate, IV solvers and Greeks. Compare calculated and provider values.

## 24. Volatility surface

Represent IV across strike × expiry. Analyze ATM IV, wings, skew/smile, term structure and forward-volatility concepts. Version inputs so historical surfaces can be reconstructed.

## 25. Options strategy research

Support payoff/research for calls/puts, verticals, straddles, strangles, iron condors, butterflies, calendars, diagonals, ratios and hedges. Evaluate payoff, max loss/profit when bounded, breakevens, margin estimate, liquidity, Greeks and scenario P&L. Probability estimates must disclose assumptions.

## 26. Independent risk engine

Risk output: APPROVE, RESIZE, REJECT, HALT.

### Trade risk

Risk per trade, stop-distance sizing, max quantity/order value, margin, liquidity/spread constraints and strategy-specific rules.

### Account risk

Daily/weekly loss, drawdown, leverage, available margin and account locks.

### Portfolio risk

Gross/net, instrument/sector/strategy exposure, beta, correlation/concentration and hedges.

### Options risk

Delta, gamma, theta, vega, expiry/short-vol concentration and scenario loss.

### Operational risk

Stale data, broker disconnect, reconciliation failure, high latency, DB failure, abnormal spread/slippage, duplicate/excessive order rate, strategy malfunction and manual locks.

Strategies never bypass risk.

## 27. Position sizing

Support fixed-risk, stop-distance, ATR/volatility and portfolio-risk sizing. A conceptual base calculation is risk capital / per-unit stop risk, then constrained by lot size, margin, liquidity and exposure. Do not treat this as a profitability guarantee.

## 28. Kill switches

Global, account, broker, strategy, instrument, new-order and close-only controls.

Potential triggers: loss/drawdown limits, feed/broker failure, reconciliation mismatch, runaway orders, unexpected exposure, reject loops, extreme slippage and manual operator action.

## 29. OMS

Durable state machine:

CREATED → RISK_PENDING → APPROVED → SUBMITTING → SUBMITTED → ACKNOWLEDGED → PARTIALLY_FILLED → FILLED.

Alternative states include REJECTED, CANCEL_PENDING, CANCELLED, MODIFY_PENDING, EXPIRED, UNKNOWN and RECONCILIATION_REQUIRED.

Persist transitions and source events. Correctly handle duplicate callbacks, timeout-after-submit, partial fills, cancel/modify races, crashes and broker disagreement.

## 30. EMS / execution

Separate what to trade from how to trade. Begin with market, limit, stop and stop-limit. Later evaluate TWAP, VWAP, POV, passive/adaptive and liquidity-aware slicing.

Measure arrival price, decision price, execution price, spread paid, slippage, implementation shortfall, fill ratio and latency.

## 31. Broker abstraction

Canonical BrokerAdapter operations:

authenticate/token lifecycle, instrument lookup/mapping, quotes, historical data, subscribe/unsubscribe, place/modify/cancel order, get order/orders/trades/positions/holdings/funds and broker update streams.

Adapters: PaperBrokerAdapter, UpstoxAdapter, DhanAdapter.

Strategy code never knows the active broker.

## 32. Reconciliation

Continuously compare internal orders ↔ broker orders, fills ↔ broker trades, positions ↔ broker positions, holdings ↔ broker holdings and funds ↔ broker funds.

Differences create incidents. Severe unresolved mismatch moves live execution to close-only/halted according to policy.

## 33. Restart recovery

Startup sequence:

Application start → DB health → broker auth → market-data health → load internal open orders/state → fetch broker orders/trades/positions/funds → reconcile → recover OMS/positions → risk validation → enable permitted trading mode.

Never allow new live orders before required reconciliation succeeds.

## 34. Paper broker

Simulate market, limit, stop, stop-limit, partial fills, slippage, spread, latency, modify, cancel and reject. Persist orders/fills/positions/funds/P&L/charges across restarts. Paper behavior should be realistic enough to expose assumptions, not optimized to make strategies look good.

## 35. Replay

Historical events → replay clock → normal market-data interfaces → features/strategy → risk → paper execution. Support pause, step and useful speed multipliers. Use replay for visual/debuggable strategy validation.

## 36. Event-driven backtesting

Model market sessions/holidays, orders, partial fills, spread, slippage, latency assumptions, brokerage/fees/taxes, liquidity, expiry, sizing, margin and relevant corporate actions. Reuse production strategy/decision/risk interfaces wherever practical.

## 37. Backtest metrics

Net return, CAGR, volatility, Sharpe, Sortino, Calmar, max drawdown, profit factor, expectancy, win/loss rates, average win/loss, payoff, exposure, turnover, trade count, holding time, MAE, MFE and recovery factor. Do not optimize primarily for win rate.

## 38. Validation framework

Research → train/development → validation → out-of-sample → walk-forward → parameter stability → Monte Carlo → stress → paper → shadow → limited deployment.

Explicitly test look-ahead, survivorship/selection bias, leakage, unrealistic fills and parameter instability.

## 39. Monte Carlo / stress

Randomize relevant trade order, slippage, missed trades, cost assumptions and return/fill effects where methodologically justified. Analyze return/drawdown/loss-streak/recovery/risk-of-ruin distributions. Historical performance never guarantees future results.

## 40. Strategy registry

Immutable strategy versions record ID/version, code hash, parameters, dataset/universe/features, author/source, creation time, backtests, validation, paper results, risk approval and deployment status.

Lifecycle: RESEARCH → CANDIDATE → VALIDATED → PAPER → SHADOW → LIMITED_LIVE → LIVE → SUSPENDED → RETIRED.

## 41. ML subsystem

Possible predictions: P(up/down), expected return, expected volatility, P(TP-before-SL), regime, signal quality, slippage/liquidity and anomalies.

Start with logistic regression, random forest, XGBoost/LightGBM after establishing baselines. Deep learning only when data/evidence justify complexity.

## 42. Feature store

Feature records need name/version, timestamp, instrument, value, lookback, source/calculation version and especially availability timestamp. Availability timing prevents research leakage.

## 43. ML training

Point-in-time data → feature generation → labels → chronological split → train → validate → calibrate → OOS → register → shadow inference → production scoring. Never casually random-shuffle financial time series.

## 44. Model registry and monitoring

Track model/version, training data, features, hyperparameters, metrics/calibration, code commit, artifact, approval and deployment. Support champion/challenger/rollback.

Monitor feature/prediction/calibration drift, realized degradation, missing features, latency and inference errors. ML influence can be disabled without breaking deterministic infrastructure.

## 45. AI assistant

Use LLMs for natural-language research, strategy/backtest explanations, journal summaries, document/news processing, analytics queries, documentation and incident/log analysis. Strategy generation should produce reviewable structured rules/DSL rather than unrestricted executable code. AI explanations must reference deterministic evidence.

## 46. Scanner

Filters may include price, volume, RVOL, ATR, volatility, gap, VWAP, EMA, RSI, breakout, BOS, CHoCH, FVG, order block, liquidity sweep, OI, IV, PCR, regime and strategy signal. Support compound rule sets.

## 47. Alerts

Potential channels: in-app, push, email, Telegram and webhook. Alert on signals, orders/fills, risk rejections, P&L/drawdown, broker/feed disconnects, reconciliation mismatch, strategy halt and incidents. Deduplicate/rate-limit noise.

## 48. Portfolio view

Cash, margin, positions, holdings, realized/unrealized P&L, gross/net exposure, beta, strategy/sector exposure and options Greeks. Support portfolio → strategy → instrument → trade drill-down.

## 49. Accounting

Calculate gross P&L, brokerage, exchange charges/taxes, slippage, net P&L, realized and unrealized values. Maintain internal accounting and reconcile it to broker records rather than treating external UI values as sole truth.

## 50. Trade journal

Automatically record setup, signal/features, chart/context references, decision, risk decision, order/fill, position, exit, P&L, MAE/MFE, strategy/version, regime and notes. Analyze by strategy/symbol/time/weekday/regime/direction/setup/volatility.

## 51. Surveillance

Detect runaway strategies, order storms, duplicate orders, reject loops, unusual turnover, unexpected positions/leverage/losses, abnormal fills/slippage, data/model anomalies and broker mismatch.

System modes: NORMAL, DEGRADED, READ_ONLY, CLOSE_ONLY, HALTED.

## 52. Observability

Structured JSON logs with trace/request/strategy/decision/order/broker/account identifiers where appropriate. Metrics for feed/API/order/fill latency, errors, reconnects, signals, risk rejects, orders, slippage, P&L and data gaps. OpenTelemetry traces should connect market event → strategy → decision → risk → order → broker → fill.

## 53. Audit trail

Append-oriented audit of market/feature evidence references, strategy/version, decision, risk resize/reject, order state, fills, configuration/control changes and operator actions. Preserve enough metadata to reconstruct why an economic action occurred.

## 54. Authentication / authorization

Secure sessions/OAuth where appropriate, MFA for sensitive operations, RBAC, least privilege and audit. Roles may include ADMIN, TRADER, RISK_MANAGER, RESEARCHER, VIEWER and SYSTEM. Sensitive live controls require elevated authorization.

## 55. Secrets

Never commit broker secrets, API keys, refresh tokens, DB passwords or private keys. Development uses safe environment injection; production uses an appropriate secret manager and rotation policy.

## 56. Environment separation

LOCAL, TEST, BACKTEST, PAPER, STAGING, LIVE. UI and API responses must make PAPER vs LIVE unmistakable. Paper and live credentials/state should not be casually interchangeable.

## 57. Live-trading gates

New live orders require all configured gates, including explicit live enablement, operator authorization, authenticated broker, healthy market data/database/risk/audit, successful reconciliation, approved strategy, capital allocation and working kill switch. Gate failure means no new live order.

## 58. Frontend workspaces

1. Command Center
2. Trading Terminal
3. Advanced Chart
4. Market Scanner
5. SMC/ICT Workspace
6. Order-Flow Workspace
7. Options Terminal
8. Strategy Lab
9. Backtest Lab
10. Replay
11. Paper Trading
12. Portfolio
13. Risk Console
14. OMS
15. Execution Analytics
16. Journal
17. ML Lab
18. Surveillance
19. System Health
20. Audit Explorer
21. Administration

No fake dashboard metrics presented as real.

## 59. Trading-terminal layout

Header: symbol/market/timeframe, PAPER/LIVE state and connectivity.

Left: watchlist/scanner/signals.

Center: chart with indicators, BOS/CHoCH/MSS, FVG/order blocks/liquidity/session levels, entries/stops/targets/fills.

Right: order ticket/book/depth/options context.

Bottom: orders, positions, trades, P&L, risk and journal.

## 60. Risk dashboard

Show equity, available margin, daily P&L, drawdown, gross/net exposure, strategy/sector exposure, beta, Greeks, limits, locks and kill switches. Risk state should be more prominent than a strategy confidence score.

## 61. Research workspace

Dataset/feature explorer, notebooks where appropriate, experiment tracking, strategy builder, backtest comparison, parameter analysis, walk-forward, Monte Carlo and model comparison. Results must remain reproducible.

## 62. Strategy DSL

Eventually support a validated declarative strategy format containing universe, bias timeframe/rules, setup, confirmation, exits and risk policy. Natural-language generation may create draft DSL, but schema validation and human/research review precede execution.

## 63. API architecture

Versioned REST groups:

`/api/v1/auth`, `/instruments`, `/market-data`, `/candles`, `/features`, `/smc`, `/scanner`, `/strategies`, `/signals`, `/backtests`, `/replay`, `/paper`, `/orders`, `/positions`, `/portfolio`, `/options`, `/risk`, `/models`, `/journal`, `/system`, `/audit`.

WebSockets: market, orders, positions, signals, risk and system.

## 64. Database architecture

Logical schemas can include reference, market, features, research, strategy, trading, risk, portfolio, options, ml, audit and system. Use Timescale/Parquet/object storage for appropriate high-volume time series/archive workloads. Do not store large tick history as arbitrary JSON blobs.

## 65. Redis responsibilities

Caching, ephemeral snapshots, rate limiting, fan-out/session state and carefully justified locks. PostgreSQL remains durable truth for critical trading state.

## 66. Domain events

Examples: TickReceived, QuoteUpdated, CandleClosed, FeatureUpdated, SignalGenerated, DecisionCreated, RiskApproved, RiskRejected, OrderCreated, OrderSubmitted, OrderAcknowledged, OrderFilled, PositionChanged, LimitBreached, ReconciliationFailed.

Initially these may execute in-process or through simple worker infrastructure. Introduce a durable bus only when requirements justify it.

## 67. Idempotency

Mandatory for ingestion, order submission semantics, broker callbacks, fill processing, position updates and reconciliation. A repeated event must not create duplicate economic effects.

## 68. Concurrency

Test fill-during-cancel, fill-during-modify, simultaneous callbacks, timeout followed by fill, restart after submission, duplicate WS update and stale snapshots. Design transaction boundaries and optimistic/pessimistic locking intentionally.

## 69. Failure engineering

Inject internet/feed/broker WS loss, REST timeouts, DB/Redis restarts, worker crashes, frontend disconnects, duplicates/out-of-order messages, broker 5xx/rate limits, partial fills, exchange rejection and clock drift. Expected behavior must be deterministic and safe.

## 70. Testing pyramid

Unit: indicators, SMC, sizing, risk, pricing, P&L, state transitions.

Integration: DB, Redis, API, ingestion, paper broker, risk→OMS.

Contract: Upstox/Dhan using safe documented capabilities/fixtures.

Property: accounting/order/risk invariants.

E2E: login/authorization where applicable → load market → signal → decision → risk → paper order → fill → position → exit → P&L → reconciliation → journal.

## 71. Critical invariants

- filled quantity never exceeds order quantity
- position changes derive from accepted fills
- no live order without required risk approval
- no new order after applicable kill switch
- no strategy bypasses OMS/risk
- duplicate fill event creates no duplicate position/economic effect
- historical decisions never use future data
- accounting and reconciliation invariants hold

Encode invariants as tests where possible.

## 72. CI pipeline

Install → formatting check → lint → type check → unit → integration → security/dependency/secret checks → frontend tests/build → selected E2E. Protect `main` as the project matures and use evidence-based releases.

## 73. Deployment

Initial deployment: reverse proxy as needed → Next.js/web → FastAPI/API → workers/scheduler → PostgreSQL/Timescale + Redis + object storage. Dockerized with separate paper/live environments. Live remains gated.

## 74. Backup / disaster recovery

Back up DB, configuration metadata, strategy/model registries, audit and critical object storage. Test restoration. A backup that has never been restored is not proven recovery.

## 75. Performance/SLO measurement

Measure feed→normalization, normalization→strategy, strategy→risk, risk→OMS, OMS→broker, broker→fill processing, UI WS latency and API p50/p95/p99. Optimize after profiling rather than guessing.

## 76. Retention

Define retention/archival for raw ticks, quotes/depth, candles, features, signals, orders/fills, audit, logs, metrics and research artifacts. Move cold analytical data to compressed/archive storage where appropriate.

## 77. Compliance-oriented architecture

Treat current Indian regulatory, exchange, broker and data-licensing requirements as a dedicated production workstream. Maintain order/audit traceability, permissions, risk controls, broker/exchange restrictions, retention and operational controls. Verify authoritative current requirements before production live release.

## 78. Production incidents

Suggested levels: SEV-1 trading safety, SEV-2 major trading degradation, SEV-3 partial degradation, SEV-4 non-critical. Maintain runbooks for broker outage, data outage, position mismatch, unexpected order, risk failure, DB outage, credential expiry and abnormal losses.

## 79. System health

Every subsystem reports HEALTHY, DEGRADED or UNAVAILABLE. Trading policy maps component health to NORMAL/DEGRADED/READ_ONLY/CLOSE_ONLY/HALTED behavior.

## 80. Control plane

Manage strategy activation, capital allocation, risk limits, broker accounts, feature flags, sessions, model promotion, kill switches, maintenance and permissions. Every sensitive change is audited.

## 81. Configuration management

Typed/versioned hierarchy: Global → Environment → Broker → Account → Strategy → Instrument. Do not scatter critical trading configuration across undocumented environment variables.

## 82. Feature flags

Examples: options engine, ML scoring, order flow, individual strategy activation. Live execution is not an ordinary feature flag; it requires stronger authorization/gating.

## 83. Capital allocation

Portfolio capital → risk budget → strategy allocation → instrument allocation → position sizing. Inputs may include volatility, drawdown, strategy correlation, liquidity, capacity and degradation state. Do not automatically scale simply because recent returns are strong.

## 84. Strategy health

Track expected vs realized behavior, return, drawdown, slippage, turnover, signal frequency, feature distribution, regime performance and execution quality. States may be NORMAL, WATCH, DEGRADED, SUSPENDED.

## 85. Execution analytics / TCA

Compare decision, arrival, submitted and average fill prices, benchmarks, spread, slippage, fees and implementation shortfall. TCA should help distinguish alpha failure from execution cost/latency problems.

## 86. Research reproducibility

A historical result should be reconstructable from Git commit, dataset/universe/feature/strategy versions, parameters, execution/cost models, random seed and environment. Backtests lacking required metadata cannot be promoted.

## 87. Advanced future modules

Only after the core is mature: cross-sectional models, stat arb, pairs/cointegration, market-neutral portfolios, factor portfolios, volatility strategies, dynamic hedging, advanced execution, alternative data, NLP event intelligence, deep time-series models, RL research, multi-broker routing and additional asset classes.

## 88. Delivery phases

### Phase 0 — Audit/control

Inspect branches, architecture, dependencies, configuration, DB, APIs, UI, tests, CI/security, TODOs, broker integrations and docs. Maintain implementation status.

### Phase 1 — Foundation

Repo/tooling, typed config, domain foundation, PostgreSQL, migrations, Redis, structured logging/tracing, health, auth/audit foundation, Docker and CI.

Gate: build/import, lint, type checks, tests, migrations and container build succeed with recorded evidence.

### Phase 2 — Market data

Instrument master, historical/live connectors, normalization, data quality, storage, reconnect/resubscribe/rate-limit behavior.

### Phase 3 — Quant engine

Candle aggregation, indicators, price action, SMC/ICT, regime and feature storage with deterministic regression tests.

### Phase 4 — Strategy platform

Strategy/alpha interfaces, decision engine, initial strategies, scanner and evidence/explanations. Still no unrestricted broker execution.

### Phase 5 — Backtesting

Event engine, order/fill simulation, costs/slippage, metrics, OOS/walk-forward/Monte Carlo and synthetic scenario validation.

### Phase 6 — Paper trading

Paper broker, OMS, positions, portfolio/P&L, journal, replay and restart recovery. Full simulated workflow works end to end.

### Phase 7 — Independent risk

Trade/account/portfolio/operational/options risk plus kill switches. Deliberately attempt to break safety invariants.

### Phase 8 — Real brokers

Upstox/Dhan auth, market data, order/modify/cancel, trades/positions/funds, broker updates and reconciliation. Begin with live execution disabled/shadow-safe workflows.

### Phase 9 — Options

Chain, OI, IV, Greeks, pricing, surface, strategies, portfolio Greeks and scenarios.

### Phase 10 — ML

Feature store, training/validation, registry, inference, monitoring and champion/challenger. Optional influence only.

### Phase 11 — Institutional frontend

Operational workspaces backed by real backend state; no fake metrics.

### Phase 12 — Failure/security validation

Failure injection, restart/broker timeout/duplicate-event/reconciliation tests, security/dependency/authz scans and load testing.

### Phase 13 — Controlled release

Backtest → replay → paper → shadow → limited live → gradual allocation. Never jump from idea/backtest directly to unrestricted live.

## 89. Definition of done

A normal feature requires implementation + persistence where needed + API/UI where needed + validation + unit/integration tests + error handling + observability + security + documentation.

Trading-critical features additionally require failure/restart behavior, idempotency, auditability and reconciliation where relevant.

Generated is not working. Mocked is not real. Untested is not tested. Local is not deployed. Pending is not complete.

## 90. Non-negotiable engineering rules

- No look-ahead bias.
- No repainting historical signals as real-time-valid signals.
- No fake broker integration.
- No mock data silently presented as live.
- No hardcoded successful order response.
- No duplicate-order vulnerability accepted as normal.
- No strategy bypassing independent risk.
- No LLM directly controlling broker execution.
- No live mode by default.
- No committed secrets.
- No untested migration promoted as safe.
- No silently ignored reconciliation mismatch.
- No profitability claims based solely on backtests.
- No production-ready/secure/fully-tested claim without evidence.

## 91. First institutional-quality vertical slice

The first objective is not maximum module count. Prove this complete path:

`Real/recorded Market Data → Data Validation → Closed Candle → Features → Deterministic SMC/ICT → Strategy → Decision → Independent Risk → OMS → Paper Execution → Fill → Position/P&L → Reconciliation → Journal → API/Dashboard → E2E`

Only after this path is deterministic, tested, restart-safe and observable should the project expand into real broker execution, advanced options, portfolio optimization, ML, order-flow and sophisticated EMS algorithms.

## 92. Vibe-coding execution protocol

The coding agent repeatedly performs:

`Understand → Inspect repository → Read blueprint/status/current phase → Prioritize highest-risk incomplete vertical slice → Research official docs when current APIs matter → Design smallest maintainable change → Implement → Run → Lint → Type-check → Test → Fix root cause → Security-check → Validate integration/E2E → Update docs/status → Continue`

Do not stop at plans or pseudocode when implementation can be safely completed. Do not create broad placeholders just to appear complete. Ask only for credentials, approval or genuinely irreversible decisions that cannot be inferred safely.

## 93. Project-control loop

`MASTER_BLUEPRINT/FULL_PROJECT_BLUEPRINT → ROADMAP → CURRENT_PHASE → NEXT_TASKS → implementation → tests/validation → IMPLEMENTATION_STATUS → commit/PR → next vertical slice`

`docs/IMPLEMENTATION_STATUS.md` is the source of truth and uses NOT_STARTED, IN_PROGRESS, IMPLEMENTED_UNVERIFIED, TESTED, BLOCKED and PRODUCTION_VALIDATED.

## 94. End-state architecture

```text
                         MARKET
                           │
            ┌──────────────┴──────────────┐
            │                             │
       Historical                       Live
            │                             │
            └──────────────┬──────────────┘
                           ↓
                  MARKET DATA PLATFORM
                           ↓
                    DATA QUALITY
                           ↓
                 POINT-IN-TIME STORE
                           ↓
                     FEATURE ENGINE
       ┌─────────┬─────────┼─────────┬─────────┐
       ↓         ↓         ↓         ↓         ↓
 Technical   SMC/ICT   OrderFlow  Options  Statistical
       └─────────┴─────────┼─────────┴─────────┘
                           ↓
                     REGIME ENGINE
                           ↓
                      ALPHA MODELS
                           ↓
                    STRATEGY ENGINE
                           ↓
                    DECISION ENGINE
                           ↓
                PORTFOLIO CONSTRUCTION
                           ↓
                 INDEPENDENT RISK
                           ↓
                 EXECUTION POLICY
                           ↓
                    OMS  →  EMS
                           ↓
                    BROKER LAYER
                    ↙             ↘
                UPSTOX            DHAN
                    ↘             ↙
                      EXCHANGE
                           ↓
                         FILLS
                           ↓
                    RECONCILIATION
                           ↓
             PORTFOLIO + P&L + ACCOUNTING
                           ↓
             JOURNAL + EXECUTION ANALYTICS
                           ↓
              SURVEILLANCE + MONITORING
                           ↓
                  RESEARCH FEEDBACK
```

This architecture is the destination. Delivery remains incremental, evidence-driven and safety-gated.
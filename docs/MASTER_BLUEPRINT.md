# Institutional Trading Platform — Master Blueprint

## 1. Objective

Build an India-first institutional-style quantitative trading platform supporting:

Research → Analyze → Scan → Replay → Backtest → Validate → Paper → Shadow → Controlled Live → Monitor → Reconcile → Journal → Improve

Initial production scope:

- NSE cash and derivatives
- NIFTY, BANKNIFTY and selected liquid NSE equities
- Intraday and swing
- Multi-timeframe analysis
- Technical indicators
- Deterministic price action and SMC/ICT
- Options intelligence
- Backtesting and replay
- Paper trading
- Independent risk controls
- Upstox and Dhan broker integration
- Controlled live execution

Architecture must remain extensible to other venues/assets without coupling the core domain to a broker.

## 2. Non-negotiable execution path

Market Data → Data Quality → Validated Features → Alpha/Strategy → Decision Engine → Portfolio Construction → Independent Risk Engine → Execution Policy → OMS/EMS → Broker Adapter → Reconciliation

LLM/ML components never directly submit orders.

## 3. Technology baseline

Backend: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, AsyncIO, HTTPX, WebSockets.

Quant: NumPy, Polars, SciPy/statsmodels where justified, scikit-learn, XGBoost/LightGBM later.

Storage: PostgreSQL, TimescaleDB, Redis, Parquet/object storage where appropriate.

Frontend: Next.js, React, TypeScript, TradingView Lightweight Charts, TanStack Query, Zustand, WebSockets.

Infra: Docker, Docker Compose, GitHub Actions, OpenTelemetry, Prometheus, Grafana.

Testing: Pytest, Ruff, MyPy, Bandit, Vitest, Playwright.

Start as a modular monolith plus background workers.

## 4. Core domain

Canonical entities include Exchange, Instrument, TradingSession, Tick, Trade, Quote, OrderBookSnapshot, Candle, FutureContract, OptionContract, OptionChain, Greeks, CorporateAction, DataQualityEvent, Signal, StrategyDecision, PortfolioDecision, RiskDecision, OrderIntent, BrokerOrder, OrderEvent, Fill, Position, Portfolio, Account, FundsSnapshot, PnLSnapshot, RiskLimit, BacktestRun, DatasetVersion, FeatureDefinition, StrategyVersion, ModelVersion, AuditEvent and Incident.

Use internal instrument IDs. Broker tokens map to them and must not leak into strategy logic.

## 5. Market data

Support historical OHLCV, live trades/quotes, depth when available, futures, option chains, OI, IV/Greeks, instrument masters, corporate actions and exchange calendars.

Pipeline:

Provider → Connector → Raw Event → Schema/sequence/time validation → Dedup/order → Normalization → Quality checks → Canonical event → Durable storage/fan-out.

Preserve source, exchange timestamp, provider timestamp, ingestion timestamp and sequence metadata when available.

Separate raw, normalized, derived/features and trading/accounting data.

## 6. Data quality

Detect missing, duplicate, out-of-order and stale events; timestamp drift; invalid prices/volume; session violations; candle gaps; mapping errors; crossed markets and provider outages.

Quality states: GOOD, DEGRADED, STALE, INVALID, MISSING.

Bad quality can produce `NO_TRADE` or an operational lock.

## 7. Multi-timeframe engine

Target 1m, 3m, 5m, 15m, 30m, 1h, 4h, 1d and 1w. Build higher timeframes from closed lower bars when appropriate and test session boundaries. Never use incomplete future data.

## 8. Feature engine

Technical indicators: SMA, EMA, WMA, RSI, MACD, ATR, ADX, Bollinger/Keltner, ROC, stochastic, VWAP/anchored VWAP, Supertrend, OBV, MFI, RVOL, pivots, Donchian and realized volatility.

Price action: swings, structure, support/resistance, breakouts, retests, ranges, compression/expansion, gaps, impulse/pullback and session highs/lows.

SMC/ICT: BOS, CHoCH, MSS, displacement, FVG/IFVG, order/mitigation/breaker blocks, equal highs/lows, BSL/SSL, liquidity sweeps, PDH/PDL/PWH/PWL, session levels, premium/discount/equilibrium, OTE, consequent encroachment and configurable sessions/kill zones.

Every SMC/ICT detector must define explicit deterministic rules, source candles, thresholds, invalidation and version. No repainting.

Order-flow features are enabled only when adequate source data exists: spread, depth/order-book imbalance, microprice, aggressor/trade imbalance, volume delta and liquidity measures. Never synthesize unavailable L2 information from OHLCV.

## 9. Regime and factors

Regimes: bull/bear trend, range, breakout/transition, high/normal/low volatility, high/low liquidity, event-risk, opening/closing and expiry.

Start deterministic; ML may augment later.

Cross-sectional factor framework may include momentum, volatility, liquidity, relative strength, beta, sector momentum, breadth and other validated factors with point-in-time universes.

## 10. Strategy and alpha framework

Strategies produce standardized alpha/signals, not broker orders. Each strategy declares metadata, data/features, universe, entry/exit/invalidation, sizing intent and explanation.

Initial candidates: trend continuation, HTF pullback, VWAP continuation, opening-range breakout, liquidity-sweep reversal, SMC FVG continuation, order-block retest, momentum breakout, range mean reversion and relative strength.

Do not enable every strategy live merely because it exists.

## 11. Decision engine

Combine validated technical, SMC/ICT, regime, volume, options, factors, optional ML, data-quality and strategy-health evidence.

Outputs: LONG, SHORT, EXIT, REDUCE, HOLD or NO_TRADE plus instrument/time, strategy/version, factors/rejections, confidence where calibrated, entry/invalidation/targets when defined, and immutable evidence snapshot ID.

## 12. Portfolio construction

Convert signals into target positions using expected risk/return, current portfolio and constraints. Support position sizing, volatility targeting, strategy/risk budgets, instrument/sector/gross/net/beta/correlation constraints and hedging.

Advanced optimizers (risk parity, min variance, CVaR, etc.) are later additions and require validation.

## 13. Options platform

Option contract/chain, OI/change OI, volume, spread, PCR, max-pain analytics where useful, IV rank/percentile, expected move, Black-Scholes/Black-76 where appropriate, IV solver and Greeks. Compare calculated versus provider Greeks rather than blindly trusting external values.

Later: IV surface, skew/smile, term structure, strategy payoff/scenarios and portfolio Greeks.

## 14. Independent risk engine

Risk is independent and returns APPROVE, RESIZE, REJECT or HALT.

Trade: risk/trade, stop sizing, quantity, liquidity/spread.

Account: daily/weekly loss, drawdown, leverage/margin.

Portfolio: gross/net/instrument/sector/strategy/beta/correlation exposure.

Options: delta/gamma/theta/vega and expiry concentration.

Operational: stale data, broker/feed disconnect, DB/reconciliation failures, abnormal spread/slippage, duplicate/excessive orders and session/event locks.

Provide global/account/broker/strategy/instrument kill switches and close-only mode.

## 15. OMS and execution

Durable order lifecycle including CREATED, RISK_PENDING, APPROVED, SUBMITTING, SUBMITTED, ACKNOWLEDGED, PARTIALLY_FILLED, FILLED, REJECTED, CANCEL_PENDING, CANCELLED, MODIFY_PENDING, EXPIRED, UNKNOWN and RECONCILIATION_REQUIRED.

Persist every economically meaningful transition. Handle timeout-after-submit, duplicate/out-of-order callbacks, partial fills, cancel/modify races and process restart.

EMS begins with market, limit, stop and stop-limit. Later evaluate TWAP/VWAP/POV/passive/adaptive execution when justified. Measure arrival price, spread, slippage, fill ratio, latency and implementation shortfall.

## 16. Broker adapters

Canonical adapter operations cover auth/token lifecycle, instrument mapping, historical/live data, subscribe/unsubscribe, place/modify/cancel, orders/trades/positions/holdings/funds and broker updates.

Initial adapters: Paper, Upstox, Dhan.

Retries are allowed only when operation semantics are safe. Never blindly retry uncertain order submission.

## 17. Reconciliation and restart recovery

Continuously compare internal orders/fills/positions/holdings/funds with broker truth. Severe mismatch causes close-only or halt.

Startup: DB health → broker auth → market-data health → load internal open state → fetch broker state → reconcile → risk validation → only then permit live trading.

## 18. Paper broker and replay

Paper broker supports market/limit/stop/stop-limit, spread/slippage/latency, partial fills, reject/cancel/modify, positions/funds/P&L/charges, duplicate protection and restart persistence.

Replay feeds historical events through the same market interfaces with pause/step/speed control so strategies/risk/paper execution can be visually debugged.

## 19. Backtesting

Event-driven and aligned with production interfaces. Model sessions/holidays, costs/taxes/fees, spread, slippage, latency assumptions, partial fills/liquidity, expiry, sizing/margin and relevant corporate actions.

Metrics include net return, CAGR, volatility, Sharpe, Sortino, Calmar, max drawdown, profit factor, expectancy, win/loss, payoff, exposure, turnover, MAE/MFE and recovery.

Validation: chronological train/validation/OOS, walk-forward, parameter stability, Monte Carlo/stress and benchmark comparisons. Explicitly prevent leakage, look-ahead, survivorship bias and impossible fills.

## 20. Strategy lifecycle

RESEARCH → CANDIDATE → VALIDATED → PAPER → SHADOW → LIMITED_LIVE → LIVE → SUSPENDED/RETIRED.

Record strategy version/code hash, parameters, dataset/features, backtests, validation, paper evidence, risk approval and deployment state.

## 21. ML platform

Optional scoring for P(up/down), expected return/volatility, TP-before-SL, regime, signal quality, liquidity/slippage and anomalies.

Point-in-time feature store → labels → chronological validation → training → calibration → OOS → model registry → shadow → production scoring → drift monitoring.

Begin with interpretable baselines, logistic regression, random forest and gradient boosting. Add complex deep models only with evidence.

Model registry records dataset/features/hyperparameters/metrics/code/artifacts/approval/deployment and supports champion/challenger/rollback.

If ML health degrades, deterministic trading infrastructure remains functional.

## 22. AI assistant

LLMs may support research, explanations, document/news processing, journal summaries, log/incident analysis and generation of reviewable strategy DSL. They must explain deterministic evidence and must not bypass execution/risk controls.

## 23. Portfolio, accounting and journal

Track cash/margin, positions/holdings, realized/unrealized P&L, gross/net/sector/strategy/beta exposure and option Greeks.

P&L includes brokerage, exchange fees/taxes, spread/slippage and net results. Reconcile with broker values rather than treating the broker UI as the only accounting source.

Journal setup, signal/evidence, decision, risk, order/fill, entry/exit, P&L, MAE/MFE, regime and notes.

## 24. Surveillance and health

Detect runaway/order storms, duplicates/reject loops, unexpected exposure/leverage/P&L, abnormal fills/slippage, data/model anomalies and broker mismatch.

Operational modes: NORMAL, DEGRADED, READ_ONLY, CLOSE_ONLY, HALTED.

Subsystem health: HEALTHY, DEGRADED, UNAVAILABLE.

## 25. Observability and audit

Structured logs, metrics and OpenTelemetry traces. Correlate market event → feature → signal → decision → risk → order → broker → fill.

Audit configuration/model/strategy versions, risk decisions, control-plane changes and order lifecycle. Audit data should be append-oriented.

## 26. Security

Least privilege, secure auth/session handling, MFA for sensitive operations where appropriate, RBAC, encryption in transit/at rest where applicable, secret management, credential rotation, validation/rate limits, audit logging and dependency/security scans.

Environments: LOCAL, TEST, BACKTEST, PAPER, STAGING, LIVE. Paper/live state must be unmistakable.

No secret or production credential in Git.

## 27. Live gates

New live orders require explicit live enablement/operator authorization, broker authentication, healthy market data/database/risk/audit, successful reconciliation, approved strategy/capital allocation and operational kill switch. Failure means no new live order.

## 28. Frontend workspaces

Command Center, Trading Terminal, Advanced Chart, Scanner, SMC/ICT, Order Flow, Options, Strategy Lab, Backtest Lab, Replay, Paper Trading, Portfolio, Risk Console, OMS, Execution Analytics, Journal, ML Lab, Surveillance, System Health, Audit and Admin.

No fake dashboard metrics presented as real.

## 29. API direction

Versioned REST resources for auth, instruments, market data/candles/features/SMC/scanner, strategies/signals/backtests/replay, paper/orders/positions/portfolio/options/risk/models/journal/system/audit.

WebSockets for market, orders, positions, signals, risk and system health.

## 30. Persistence and events

PostgreSQL is durable source of truth for critical trading state. TimescaleDB/Parquet/object storage handle appropriate time-series/archive workloads. Redis is for caching, rate limits, ephemeral snapshots/fan-out and carefully designed locks—not sole durable trading truth.

Domain events include TickReceived, CandleClosed, FeatureUpdated, SignalGenerated, DecisionCreated, RiskApproved/Rejected, OrderCreated/Submitted/Acknowledged/Filled, PositionChanged, LimitBreached and ReconciliationFailed.

Critical ingestion/order/fill/reconciliation paths must be idempotent.

## 31. Testing

Unit: indicators, SMC, pricing, P&L, sizing, risk and order state transitions.

Integration: DB/Redis/API/ingestion/paper/risk→OMS.

Contract: Upstox/Dhan against safe fixtures/sandbox capabilities where available.

Property tests: accounting/order/risk invariants.

E2E: load market → signal → decision → risk → paper order → fill → position → exit → P&L → reconciliation → journal.

Failure tests: feed/broker loss, timeouts, DB/Redis restart, worker crash, duplicate/out-of-order messages, partial fills, rate limits and clock issues.

Critical invariants include: no fill > order quantity, positions derive from fills, no live order without risk approval, no order after global kill, no duplicate economic fill, no future candle in historical decisions and accounting reconciliation.

## 32. CI/CD

Every PR: formatting → lint → types → unit → integration → security/dependency scans → frontend tests/build → selected E2E.

Protected main and evidence-based release promotion. Live deployment remains explicitly gated.

## 33. Delivery phases

0. Audit/status/control files
1. Foundation: config/domain/DB/Redis/logging/health/auth/audit/Docker/CI
2. Instrument master + market data + data quality
3. Candle aggregation + indicators + price action + SMC/ICT + regime
4. Strategy/alpha + decision + scanner
5. Event-driven backtest + validation
6. Paper broker + OMS + portfolio/P&L/journal + replay
7. Independent risk + kill switches
8. Upstox/Dhan + durable execution/reconciliation
9. Options intelligence
10. ML platform
11. Operational frontend/E2E
12. Failure/security/load validation
13. Shadow → limited live → controlled scale

## 34. Definition of done

A feature is complete only when required implementation, persistence, API/UI, tests, error handling, observability, security and documentation are present and validated.

Trading-critical features additionally require idempotency, failure/restart behaviour, auditability and reconciliation where applicable.

## 35. First end-to-end target

Real/recorded market data → validated candle → features → deterministic SMC/ICT → strategy → decision → independent risk → OMS → paper execution → fill → position/P&L → reconciliation → journal → API/dashboard.

Prove this vertical slice before adding unrestricted breadth.

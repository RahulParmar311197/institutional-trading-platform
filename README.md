# Institutional Trading Platform

Institutional-style, India-first quantitative trading platform.

## Target workflow

Research → Analyze → Scan → Replay → Backtest → Validate → Paper Trade → Shadow Trade → Controlled Live Trade → Monitor → Reconcile → Improve

## Core architecture

Market Data → Data Quality → Feature Engine → Strategy/Alpha → Decision Engine → Portfolio Construction → Independent Risk → OMS/EMS → Broker Adapter → Reconciliation → Portfolio/P&L/Journal

## Initial scope

- NSE cash and derivatives
- NIFTY, BANKNIFTY and selected liquid NSE equities
- Intraday and swing strategies
- Technical indicators and deterministic SMC/ICT
- Backtesting, replay and paper trading
- Independent risk engine
- Upstox and Dhan adapters after the paper path is validated
- Options analytics and ML in later phases

## Safety

Live trading is disabled by default. Strategies and AI/ML cannot bypass deterministic risk, OMS, execution policy, or reconciliation.

## Project control

Read these before implementation:

1. `AGENTS.md`
2. `docs/MASTER_BLUEPRINT.md`
3. `docs/IMPLEMENTATION_STATUS.md`
4. `plans/CURRENT_PHASE.md`
5. `plans/NEXT_TASKS.md`

Generated code is not considered working until it has been built, tested and validated.
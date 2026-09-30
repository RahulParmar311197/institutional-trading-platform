# Current Phase

## Phase 5 — Event-driven research, external read-only data and failure hardening

Status: `IN_PROGRESS`

### Validated milestone

The deterministic paper/replay/research vertical slice remains green on `main`:

Recorded events / local JSONL / provider historical bars → normalization → closed candles → versioned strategy identity → TradingDecision → independent risk → OMS/paper execution → position/P&L → audit/reconciliation/recovery.

Canonical read-only historical slices remain validated for Upstox and Dhan cash/derivative daily data. Dhan derivative routing requires explicit persisted provider metadata; identifier rollovers and classification mismatches fail before HTTP. The Dhan compact-master boundary remains MockTransport + real-PostgreSQL tested; no live transfer or credentialed-provider success is claimed.

Research restartability and reproducibility now include:

- atomic replay checkpoints plus full-state deterministic backtest checkpoints;
- checkpoint economic/pipeline/replay-prefix consistency validation and atomic failed restore;
- versioned regime feature identity with instrument/event-time provenance;
- timezone-aware half-open dataset boundaries with UTC-canonical identity;
- explicit regular return periods with no inferred annualization;
- deterministic rolling walk-forward folds with optional embargo and deterministic fold IDs;
- OOS provenance/result identities binding boundary, fold/spec, strategy, features, normalized stream, backtest configuration and execution assumptions;
- explicit Sharpe/Sortino conventions with mandatory `periods_per_year`;
- fixed-strategy cold-start OOS fold evaluation that rejects any train/out-of-window event rather than silently filtering it.

Persistent control recovery now has an explicit initialization contract. Migration `0007` seeds singleton operational state as `NORMAL` only when missing and preserves existing state. After migration, a missing singleton is treated as corruption: load and mode updates fail closed. Persisted global/non-global risk-lock storage-key encodings are also validated and malformed rows are rejected.

### Safety controls already validated

- live trading disabled by default; no real order adapter
- deny-by-default live-trading gate
- global/account/strategy/instrument kill switches
- READ_ONLY/CLOSE_ONLY/HALTED operational modes
- migration-backed persistence/recovery of operational mode and risk locks
- missing/corrupt persisted operational control state fails closed
- health-driven restrictions persist and healthy state never auto-relaxes operator controls
- transactional rollback/no in-memory economic publication on duplicate fill, audit failure or unavailable database
- bounded transient-only provider retries; auth/client failures are not retried
- provider-master conflicts, redirects, oversized responses and malformed data fail closed
- replay/backtest malformed, mismatched and internally inconsistent checkpoints fail closed
- research partitions/returns/folds enforce explicit time and leakage boundaries
- runtime container import smoke after production-only dependency install

### Quant/research foundation already validated

- canonical instrument/provider identifiers and migration `0006` classification metadata
- Upstox/Dhan read-only historical contracts and canonical daily orchestration using mocked HTTP plus PostgreSQL
- deterministic replay, full-state backtest resume, fees/slippage/risk rejection/no-look-ahead tests
- session-aligned candles; SMA/EMA/RSI/ATR/VWAP; BOS/CHoCH/FVG/MSS/regime
- immutable strategy identity/registry lifecycle
- versioned regime feature outputs
- versioned dataset, return-period, walk-forward fold and OOS-result provenance contracts
- fixed-strategy cold-start OOS evaluation
- explicit Sharpe/Sortino calculations

### Current objective

Continue failure hardening and build leakage-safe research reporting on immutable per-fold results. Keep provider validation claims distinct from mocked integrations and preserve all live-trading safety boundaries.

Immediate work:

1. Continue persistence/network/provider fault injection around recovery/control-state transitions, including malformed persisted mode/scope and unavailable-database recovery cases where coverage is distinct.
2. Add aggregate walk-forward reporting only after explicit compatibility/order semantics are defined over immutable per-fold result identities; do not rank/select strategies.
3. Define an explicit warm-up/fitted-state transfer contract before allowing training-window-derived state into OOS evaluation.
4. Extend versioned feature outputs only when the next feature has an explicit event-time/reproducibility boundary.
5. Validate an actual Dhan compact-master transfer only in an environment that can consume the octet-stream response; add credentialed historical smoke tests only with securely supplied runtime credentials.

### Engineering gates

Every addition must keep `main` green across Ruff, strict MyPy, PostgreSQL migrations when applicable, the full unit/integration suite, Bandit, migration rollback/reapply, Docker build and runtime smoke.

### Explicitly out of scope for the current phase

- unrestricted live order placement or any real broker order submission
- broker credentials in source control
- optimizer-driven parameter selection/ranking before leakage-safe evaluation/aggregation semantics exist
- distributed orchestration without a concrete workload
- ML-controlled execution
- profitability claims
- Kubernetes/microservice expansion

### Safety invariant

Live trading remains disabled. No external adapter or future execution path may bypass data quality, canonical instrument mapping, decision, independent risk, OMS, audit, reconciliation, persisted controls, operational health or the explicit live gate.

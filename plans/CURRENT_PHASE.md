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
- fixed-strategy cold-start OOS fold evaluation that rejects any train/out-of-window event rather than silently filtering it;
- immutable fold-level aggregate reporting with compatibility/order validation and UTC-canonical report identity; overlapping folds are never compounded into a synthetic portfolio path;
- explicit warm-up/fitted-state provenance binding fold, source window, normalized source stream, strategy/features and serialized state digest;
- bounded versioned closed-candle warm-state serialization/restoration bound to strategy, instrument and interval;
- deliberate exclusion of an incomplete source-window candle from warm-state transfer so the first test event cannot close a pre-test candle and emit a contaminated OOS decision;
- warm OOS execution that restores only compatible closed pre-test history and binds the preparation-state identity to the OOS result;
- deterministic fit/embargo/validation splits wholly inside the parent training window;
- validation-only backtest result/provenance envelopes and objective-bound scores;
- deterministic candidate selection with fold/objective/direction binding and stable tie-breaking;
- selected OOS evaluation that requires the test backtester candidate to match the validation decision before the test fold can run;
- combined selected+warm OOS execution that validates the selected candidate first, then applies compatible train-derived closed-candle history, and binds decision/candidate/preparation/OOS identities in one immutable result;
- deterministic explicit-candidate validation search that rejects duplicate candidate identities and test-window events, runs candidates in stable identity order and emits candidate-set/search identities plus the existing selection decision.

Persistent control recovery has an explicit initialization contract. Migration `0007` seeds singleton operational state as `NORMAL` only when missing and preserves existing state. All persisted-control load and mutation paths require that singleton. Missing state, invalid persisted mode/scope, malformed lock-key encodings and database unavailability fail closed.

### Safety controls already validated

- live trading disabled by default; no real order adapter
- deny-by-default live-trading gate
- global/account/strategy/instrument kill switches
- READ_ONLY/CLOSE_ONLY/HALTED operational modes
- migration-backed persistence/recovery of operational mode and risk locks
- missing/corrupt/unavailable persisted operational control state fails closed before load/mutation succeeds
- health-driven restrictions persist and healthy state never auto-relaxes operator controls
- transactional rollback/no in-memory economic publication on duplicate fill, audit failure or unavailable database
- bounded transient-only provider retries; auth/client failures are not retried
- provider-master conflicts, redirects, oversized responses and malformed data fail closed
- replay/backtest malformed, mismatched and internally inconsistent checkpoints fail closed
- research partitions/returns/folds enforce explicit time and leakage boundaries
- warm OOS imports closed pre-test history only; incomplete train candles are never carried across the boundary
- validation search accepts validation-window evidence only and rejects duplicate candidate identities
- combined selected+warm OOS does not let preparation state change which candidate validation selected
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
- fold-level walk-forward aggregate reports without cross-fold path compounding
- warm-up/fitted-state provenance
- closed-candle warm-state serialization/restoration and warm OOS execution
- leakage-safe fit/validation splitting and real validation-backtest evidence
- objective-bound deterministic validation selection and selection-bound OOS execution
- combined selected+warm OOS execution with immutable decision/preparation/result identity binding
- deterministic validation candidate-set search using real backtester results

### Current objective

Continue failure hardening only where a distinct fail-closed invariant is missing, and deepen leakage-safe research execution without allowing training/validation/test contamination. Keep provider validation claims distinct from mocked integrations and preserve all live-trading safety boundaries.

Immediate work:

1. Add an explicit deterministic parameter-grid specification/generator and multi-fold search orchestration on top of the tested explicit-candidate validation search; test-fold outcomes must never select or tune their own configuration.
2. Define generic fitted/model/feature-state export-import only when a stateful research component actually requires it; the current tested warm path is specifically closed-candle history for stateless strategy evaluation.
3. Extend selected/warm OOS aggregate reporting only if per-fold selection-decision and preparation-state identities remain explicit and overlapping folds are never synthesized into one path.
4. Continue persistence/network/provider fault injection only where a distinct fail-closed invariant remains untested; avoid duplicate synthetic cases now that control missing/corrupt/unavailable paths are covered.
5. Extend versioned feature outputs only when the next feature has an explicit event-time/reproducibility boundary.
6. Validate an actual Dhan compact-master transfer only in an environment that can consume the octet-stream response; add credentialed historical smoke tests only with securely supplied runtime credentials.

### Engineering gates

Every addition must keep `main` green across Ruff, strict MyPy, PostgreSQL migrations when applicable, the full unit/integration suite, Bandit, migration rollback/reapply, Docker build and runtime smoke.

### Explicitly out of scope for the current phase

- unrestricted live order placement or any real broker order submission
- broker credentials in source control
- representing closed-candle warm-up as arbitrary fitted/model-state restoration
- test-fold-driven parameter selection or optimizer ranking
- distributed orchestration without a concrete workload
- ML-controlled execution
- profitability claims
- Kubernetes/microservice expansion

### Safety invariant

Live trading remains disabled. No external adapter or future execution path may bypass data quality, canonical instrument mapping, decision, independent risk, OMS, audit, reconciliation, persisted controls, operational health or the explicit live gate.

import json
import os
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from test_backtest import make_backtester, sample_events

from trading_platform.backtest import BacktestCheckpoint, BacktestCheckpointFileStore
from trading_platform.pipeline import ReplayPipelineState
from trading_platform.recorded_events import normalize_recorded_events


def test_checkpoint_rejects_internally_inconsistent_fees() -> None:
    session = make_backtester().create_session(sample_events())
    session.step(4)
    checkpoint = session.checkpoint()

    payload = json.loads(checkpoint.to_json())
    payload["total_fees"] = "1"

    with pytest.raises(ValueError, match="total_fees"):
        BacktestCheckpoint.from_json(json.dumps(payload))


def test_restore_rejects_pipeline_state_not_matching_replay_prefix_atomically() -> None:
    events = sample_events()
    session = make_backtester().create_session(events)
    session.step(1)
    before = session.checkpoint()

    source = make_backtester().create_session(events)
    source.step(3)
    checkpoint = source.checkpoint()
    corrupted = replace(
        checkpoint,
        pipeline_state=ReplayPipelineState(
            closed_candles=(),
            pending_trades=checkpoint.pipeline_state.pending_trades,
        ),
    )

    with pytest.raises(ValueError, match="pipeline state"):
        session.restore(corrupted)

    assert session.checkpoint() == before


def test_restore_rejects_equity_prefix_mismatch_atomically() -> None:
    events = sample_events()
    session = make_backtester().create_session(events)
    session.step(1)
    before = session.checkpoint()

    source = make_backtester().create_session(events)
    source.step(3)
    checkpoint = source.checkpoint()
    wrong_point = replace(checkpoint.equity_curve[0], mark_price=Decimal("999"))
    corrupted = replace(
        checkpoint,
        equity_curve=(wrong_point, *checkpoint.equity_curve[1:]),
    )

    with pytest.raises(ValueError, match="equity curve"):
        session.restore(corrupted)

    assert session.checkpoint() == before


def test_interrupted_checkpoint_replace_preserves_last_good_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events = sample_events()
    first = make_backtester().create_session(events)
    first.step(2)
    store = BacktestCheckpointFileStore(tmp_path / "state.json")
    store.save(first.checkpoint())
    original_bytes = store.path.read_bytes()

    second = make_backtester().create_session(events)
    second.step(4)

    def fail_replace(*_args: object) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        store.save(second.checkpoint())

    assert store.path.read_bytes() == original_bytes
    assert store.load() == first.checkpoint()
    assert list(tmp_path.glob(".state.json.*.tmp")) == []


def test_checkpoint_pipeline_state_matches_normalized_prefix() -> None:
    events = sample_events()
    normalized = normalize_recorded_events(events)
    session = make_backtester().create_session(events)
    session.step(3)

    checkpoint = session.checkpoint()
    assert checkpoint.replay.cursor == 3
    assert [point.event_id for point in checkpoint.equity_curve] == [
        event.event_id for event in normalized[:3]
    ]
    assert checkpoint.pipeline_state.closed_candles[-1].end <= (
        normalized[2].exchange_timestamp + timedelta(minutes=1)
    )

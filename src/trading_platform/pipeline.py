import uuid
from dataclasses import dataclass
from datetime import timedelta

from trading_platform.candles import Candle, CandleBuilder
from trading_platform.decision import TradingDecision, decide
from trading_platform.recorded_events import RecordedMarketEvent
from trading_platform.replay import ReplayStream
from trading_platform.strategy import StrategyEvaluator, StrategySignal


@dataclass(frozen=True, slots=True)
class PipelineStep:
    event_id: str
    closed_candle: Candle | None
    signal: StrategySignal | None
    decision: TradingDecision | None


class ReplayStrategyPipeline:
    def __init__(
        self,
        *,
        instrument_id: uuid.UUID,
        interval: timedelta,
        strategy: StrategyEvaluator,
    ) -> None:
        self.instrument_id = instrument_id
        self.interval = interval
        self.strategy = strategy
        self._builder = CandleBuilder(instrument_id, interval=interval)
        self._closed_candles: list[Candle] = []

    @property
    def closed_candles(self) -> tuple[Candle, ...]:
        return tuple(self._closed_candles)

    def reset(self) -> None:
        self._builder = CandleBuilder(self.instrument_id, interval=self.interval)
        self._closed_candles.clear()

    def process_event(self, event: RecordedMarketEvent) -> PipelineStep:
        if event.instrument_id != self.instrument_id:
            raise ValueError("event instrument does not match replay pipeline")

        closed_candle = self._builder.add(event.to_trade())
        if closed_candle is None:
            return PipelineStep(event.event_id, None, None, None)

        self._closed_candles.append(closed_candle)
        if len(self._closed_candles) < self.strategy.minimum_history:
            return PipelineStep(event.event_id, closed_candle, None, None)

        signal = self.strategy.evaluate(list(self._closed_candles))
        decision = decide(signal)
        return PipelineStep(event.event_id, closed_candle, signal, decision)

    def run(self, events: list[RecordedMarketEvent]) -> tuple[PipelineStep, ...]:
        replay = ReplayStream.from_events(events)
        results: list[PipelineStep] = []
        while (event := replay.next_event()) is not None:
            results.append(self.process_event(event))
        return tuple(results)

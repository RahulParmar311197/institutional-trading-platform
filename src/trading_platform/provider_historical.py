import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any, cast
from urllib.parse import quote

import httpx

_SAFE_RETRY_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class HistoricalBar:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    open_interest: int | None
    source: str

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("historical bar timestamp must be timezone-aware")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("OHLC prices must be positive")
        if self.high < self.low:
            raise ValueError("high must be greater than or equal to low")
        if self.open > self.high or self.close > self.high:
            raise ValueError("open and close must not exceed high")
        if self.open < self.low or self.close < self.low:
            raise ValueError("open and close must not be below low")
        if self.volume < 0:
            raise ValueError("volume must be non-negative")
        if self.open_interest is not None and self.open_interest < 0:
            raise ValueError("open interest must be non-negative")
        if not self.source.strip():
            raise ValueError("historical bar source must not be empty")


@dataclass(frozen=True, slots=True)
class HistoricalRetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 2.0
    retry_status_codes: frozenset[int] = frozenset({429, 500, 502, 503, 504})

    def __post_init__(self) -> None:
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if self.max_attempts > 10:
            raise ValueError("max_attempts must not exceed 10")
        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds must be non-negative")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds must be >= base_delay_seconds")
        if not self.retry_status_codes.issubset(_SAFE_RETRY_STATUS_CODES):
            raise ValueError("retry_status_codes must contain transient HTTP statuses only")

    def delay_for_retry(self, retry_number: int) -> float:
        if retry_number <= 0:
            raise ValueError("retry_number must be positive")
        exponential_delay = self.base_delay_seconds * (2.0 ** (retry_number - 1))
        return min(self.max_delay_seconds, exponential_delay)


class UpstoxHistoricalUnit(StrEnum):
    MINUTES = "minutes"
    HOURS = "hours"
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"


class UpstoxHistoricalClient:
    base_url = "https://api.upstox.com/v3"

    def __init__(
        self,
        *,
        access_token: str,
        http_client: httpx.AsyncClient,
        retry_policy: HistoricalRetryPolicy | None = None,
    ) -> None:
        if not access_token.strip():
            raise ValueError("access_token must not be empty")
        self._access_token = access_token
        self._http = http_client
        self._retry_policy = retry_policy or HistoricalRetryPolicy()

    async def fetch(
        self,
        *,
        instrument_key: str,
        unit: UpstoxHistoricalUnit,
        interval: int,
        from_date: date,
        to_date: date,
    ) -> tuple[HistoricalBar, ...]:
        if not instrument_key.strip():
            raise ValueError("instrument_key must not be empty")
        _validate_upstox_interval(unit, interval)
        if from_date > to_date:
            raise ValueError("from_date must not be after to_date")

        encoded_instrument = quote(instrument_key, safe="")
        url = (
            f"{self.base_url}/historical-candle/{encoded_instrument}/"
            f"{unit.value}/{interval}/{to_date.isoformat()}/{from_date.isoformat()}"
        )

        async def request() -> httpx.Response:
            return await self._http.get(
                url,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self._access_token}",
                },
            )

        response = await _request_with_retry(request, self._retry_policy)
        payload: object = response.json()
        if not isinstance(payload, dict) or payload.get("status") != "success":
            raise ValueError("unexpected Upstox historical response")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError("Upstox historical response missing data")
        candles = data.get("candles")
        if not isinstance(candles, list):
            raise ValueError("Upstox historical response missing candles")

        bars = tuple(_parse_upstox_candle(item) for item in candles)
        return tuple(sorted(bars, key=lambda item: item.timestamp))


def _validate_upstox_interval(unit: UpstoxHistoricalUnit, interval: int) -> None:
    if unit is UpstoxHistoricalUnit.MINUTES and 1 <= interval <= 300:
        return
    if unit is UpstoxHistoricalUnit.HOURS and 1 <= interval <= 5:
        return
    if (
        unit
        in {
            UpstoxHistoricalUnit.DAYS,
            UpstoxHistoricalUnit.WEEKS,
            UpstoxHistoricalUnit.MONTHS,
        }
        and interval == 1
    ):
        return
    raise ValueError("invalid interval for Upstox historical unit")


def _parse_upstox_candle(raw: object) -> HistoricalBar:
    if not isinstance(raw, list) or len(raw) < 6:
        raise ValueError("invalid Upstox candle")
    timestamp = datetime.fromisoformat(str(raw[0]))
    open_interest = int(raw[6]) if len(raw) > 6 and raw[6] is not None else None
    return HistoricalBar(
        timestamp=timestamp,
        open=Decimal(str(raw[1])),
        high=Decimal(str(raw[2])),
        low=Decimal(str(raw[3])),
        close=Decimal(str(raw[4])),
        volume=int(raw[5]),
        open_interest=open_interest,
        source="upstox_v3_historical",
    )


class DhanHistoricalClient:
    base_url = "https://api.dhan.co/v2"
    intraday_intervals = frozenset({1, 5, 15, 25, 60})

    def __init__(
        self,
        *,
        access_token: str,
        http_client: httpx.AsyncClient,
        retry_policy: HistoricalRetryPolicy | None = None,
    ) -> None:
        if not access_token.strip():
            raise ValueError("access_token must not be empty")
        self._access_token = access_token
        self._http = http_client
        self._retry_policy = retry_policy or HistoricalRetryPolicy()

    async def fetch_daily(
        self,
        *,
        security_id: str,
        exchange_segment: str,
        instrument: str,
        from_date: date,
        to_date: date,
        expiry_code: int = 0,
        include_open_interest: bool = False,
    ) -> tuple[HistoricalBar, ...]:
        if from_date >= to_date:
            raise ValueError("Dhan daily to_date is non-inclusive and must follow from_date")
        payload: dict[str, object] = {
            "securityId": _required_text(security_id, "security_id"),
            "exchangeSegment": _required_text(exchange_segment, "exchange_segment"),
            "instrument": _required_text(instrument, "instrument"),
            "expiryCode": expiry_code,
            "oi": include_open_interest,
            "fromDate": from_date.isoformat(),
            "toDate": to_date.isoformat(),
        }
        response = await self._post("/charts/historical", payload)
        return _parse_dhan_bars(response, source="dhan_v2_daily")

    async def fetch_intraday(
        self,
        *,
        security_id: str,
        exchange_segment: str,
        instrument: str,
        interval_minutes: int,
        from_datetime: datetime,
        to_datetime: datetime,
        include_open_interest: bool = False,
    ) -> tuple[HistoricalBar, ...]:
        if interval_minutes not in self.intraday_intervals:
            raise ValueError("Dhan intraday interval must be one of 1, 5, 15, 25, 60")
        if from_datetime.tzinfo is not None or to_datetime.tzinfo is not None:
            raise ValueError("Dhan intraday request datetimes must be provider-local naive values")
        if from_datetime >= to_datetime:
            raise ValueError("from_datetime must precede to_datetime")
        if to_datetime - from_datetime > timedelta(days=90):
            raise ValueError("Dhan intraday requests are limited to 90 days")

        payload: dict[str, object] = {
            "securityId": _required_text(security_id, "security_id"),
            "exchangeSegment": _required_text(exchange_segment, "exchange_segment"),
            "instrument": _required_text(instrument, "instrument"),
            "interval": str(interval_minutes),
            "oi": include_open_interest,
            "fromDate": from_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "toDate": to_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        }
        response = await self._post("/charts/intraday", payload)
        return _parse_dhan_bars(response, source="dhan_v2_intraday")

    async def _post(self, path: str, payload: dict[str, object]) -> dict[str, Any]:
        async def request() -> httpx.Response:
            return await self._http.post(
                f"{self.base_url}{path}",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "access-token": self._access_token,
                },
                json=payload,
            )

        response = await _request_with_retry(request, self._retry_policy)
        raw: object = response.json()
        if not isinstance(raw, dict):
            raise ValueError("unexpected Dhan historical response")
        return cast(dict[str, Any], raw)


async def _request_with_retry(
    request: Callable[[], Awaitable[httpx.Response]],
    policy: HistoricalRetryPolicy,
) -> httpx.Response:
    for attempt in range(1, policy.max_attempts + 1):
        try:
            response = await request()
        except httpx.TransportError:
            if attempt == policy.max_attempts:
                raise
        else:
            if response.status_code not in policy.retry_status_codes:
                response.raise_for_status()
                return response
            if attempt == policy.max_attempts:
                response.raise_for_status()

        await asyncio.sleep(policy.delay_for_retry(attempt))

    raise RuntimeError("historical read retry loop exhausted unexpectedly")


def _required_text(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


def _parse_dhan_bars(
    payload: dict[str, Any],
    *,
    source: str,
) -> tuple[HistoricalBar, ...]:
    required = ("open", "high", "low", "close", "volume", "timestamp")
    series: dict[str, list[Any]] = {}
    for key in required:
        value = payload.get(key)
        if not isinstance(value, list):
            raise ValueError(f"Dhan historical response missing {key}")
        series[key] = value

    lengths = {len(series[key]) for key in required}
    if len(lengths) != 1:
        raise ValueError("Dhan historical response arrays have inconsistent lengths")
    count = lengths.pop()

    open_interest_raw = payload.get("open_interest")
    if open_interest_raw is None:
        open_interest: list[Any] | None = None
    elif isinstance(open_interest_raw, list) and len(open_interest_raw) == count:
        open_interest = open_interest_raw
    else:
        raise ValueError("Dhan open_interest length does not match candle arrays")

    bars = [
        HistoricalBar(
            timestamp=datetime.fromtimestamp(int(series["timestamp"][index]), tz=UTC),
            open=Decimal(str(series["open"][index])),
            high=Decimal(str(series["high"][index])),
            low=Decimal(str(series["low"][index])),
            close=Decimal(str(series["close"][index])),
            volume=int(series["volume"][index]),
            open_interest=(
                int(open_interest[index])
                if open_interest is not None and open_interest[index] is not None
                else None
            ),
            source=source,
        )
        for index in range(count)
    ]
    return tuple(sorted(bars, key=lambda item: item.timestamp))

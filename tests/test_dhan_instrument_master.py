import httpx
import pytest

from trading_platform.dhan_instrument_master import (
    DHAN_COMPACT_MASTER_URL,
    DhanCompactMasterFetcher,
    DhanInstrumentMasterConflictError,
    DhanInstrumentMasterError,
    DhanInstrumentMasterRecord,
    parse_dhan_compact_instrument_master,
)

HEADER = (
    "SEM_SMST_SECURITY_ID,SEM_EXM_EXCH_ID,SEM_SEGMENT,"
    "SEM_INSTRUMENT_NAME,SEM_EXPIRY_CODE\n"
)


def test_parse_dhan_compact_master_extracts_supported_classification() -> None:
    content = HEADER + "\n".join(
        [
            "101,NSE,E,EQUITY,",
            "202,NSE,D,FUTIDX,1.0",
            "303,BSE,D,OPTSTK,2",
            "404,MCX,M,FUTCOM,0",
        ]
    )

    records = parse_dhan_compact_instrument_master(content)

    assert records == (
        DhanInstrumentMasterRecord("101", "NSE_EQ", "EQUITY", None),
        DhanInstrumentMasterRecord("202", "NSE_FNO", "FUTIDX", 1),
        DhanInstrumentMasterRecord("303", "BSE_FNO", "OPTSTK", 2),
    )


def test_parse_dhan_compact_master_rejects_missing_required_column() -> None:
    with pytest.raises(DhanInstrumentMasterError, match="missing required columns"):
        parse_dhan_compact_instrument_master(
            "SEM_SMST_SECURITY_ID,SEM_EXM_EXCH_ID\n101,NSE\n"
        )


def test_parse_dhan_compact_master_rejects_conflicting_duplicate_security_id() -> None:
    content = HEADER + "\n".join(
        [
            "101,NSE,E,EQUITY,",
            "101,NSE,D,FUTSTK,0",
        ]
    )

    with pytest.raises(DhanInstrumentMasterConflictError, match="security ID 101"):
        parse_dhan_compact_instrument_master(content)


def test_parse_dhan_compact_master_rejects_schema_drift_on_supported_rows() -> None:
    with pytest.raises(DhanInstrumentMasterError, match="invalid instrument"):
        parse_dhan_compact_instrument_master(
            HEADER + "101,NSE,D,NEW_PROVIDER_ENUM,0\n"
        )

    with pytest.raises(DhanInstrumentMasterError, match="unsupported expiry code"):
        parse_dhan_compact_instrument_master(
            HEADER + "101,NSE,D,FUTSTK,9\n"
        )

    with pytest.raises(DhanInstrumentMasterError, match="unsupported Dhan master segment"):
        parse_dhan_compact_instrument_master(
            HEADER + "101,NSE,X,EQUITY,\n"
        )


@pytest.mark.asyncio
async def test_dhan_compact_master_fetcher_uses_exact_official_url_and_parses_bom() -> None:
    content = ("\ufeff" + HEADER + "101,NSE,E,EQUITY,\n").encode("utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == DHAN_COMPACT_MASTER_URL
        assert "text/csv" in request.headers["Accept"]
        return httpx.Response(200, content=content, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        records = await DhanCompactMasterFetcher(http_client=http).fetch_records()

    assert records == (DhanInstrumentMasterRecord("101", "NSE_EQ", "EQUITY", None),)


@pytest.mark.asyncio
async def test_dhan_compact_master_fetcher_rejects_redirects() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            302,
            headers={"Location": "https://example.invalid/master.csv"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(DhanInstrumentMasterError, match="redirected unexpectedly"):
            await DhanCompactMasterFetcher(http_client=http).fetch_text()

    assert calls == 1


@pytest.mark.asyncio
async def test_dhan_compact_master_fetcher_rejects_oversized_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"12345", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(DhanInstrumentMasterError, match="maximum size"):
            await DhanCompactMasterFetcher(http_client=http, max_bytes=4).fetch_text()


@pytest.mark.asyncio
async def test_dhan_compact_master_fetcher_rejects_invalid_utf8_and_empty_body() -> None:
    responses = [b"\xff", b""]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=responses.pop(0), request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        fetcher = DhanCompactMasterFetcher(http_client=http)
        with pytest.raises(DhanInstrumentMasterError, match="valid UTF-8"):
            await fetcher.fetch_text()
        with pytest.raises(DhanInstrumentMasterError, match="response is empty"):
            await fetcher.fetch_text()


def test_dhan_compact_master_fetcher_rejects_invalid_limits() -> None:
    http = httpx.AsyncClient()
    try:
        with pytest.raises(ValueError, match="max_bytes"):
            DhanCompactMasterFetcher(http_client=http, max_bytes=0)
        with pytest.raises(ValueError, match="timeout_seconds"):
            DhanCompactMasterFetcher(http_client=http, timeout_seconds=0)
    finally:
        # Construction does not perform I/O. Avoid leaking the client in this sync test.
        import asyncio

        asyncio.run(http.aclose())

import pytest

from trading_platform.dhan_instrument_master import (
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

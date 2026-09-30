from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from trading_platform.control_repository import RiskControlRepository
from trading_platform.controls import KillSwitchScope, OperationalMode, RiskLock

pytestmark = pytest.mark.asyncio


def unavailable_error() -> OperationalError:
    return OperationalError(
        "select operational_state",
        {},
        OSError("simulated control database connection failure"),
    )


def unavailable_session() -> tuple[AsyncSession, AsyncMock, AsyncMock]:
    get = AsyncMock(side_effect=unavailable_error())
    scalars = AsyncMock()
    raw = MagicMock()
    raw.get = get
    raw.scalars = scalars
    return cast(AsyncSession, raw), get, scalars


async def test_control_load_fails_closed_when_database_is_unavailable() -> None:
    session, get, scalars = unavailable_session()

    with pytest.raises(OperationalError, match="control database connection failure"):
        await RiskControlRepository(session).load()

    get.assert_awaited_once()
    scalars.assert_not_awaited()


async def test_control_mode_mutation_fails_before_change_when_database_is_unavailable() -> None:
    session, get, scalars = unavailable_session()

    with pytest.raises(OperationalError, match="control database connection failure"):
        await RiskControlRepository(session).persist_mode(OperationalMode.HALTED)

    get.assert_awaited_once()
    scalars.assert_not_awaited()


async def test_control_lock_mutations_fail_before_change_when_database_is_unavailable() -> None:
    session, get, scalars = unavailable_session()
    repository = RiskControlRepository(session)

    with pytest.raises(OperationalError, match="control database connection failure"):
        await repository.persist_lock(
            RiskLock(
                scope=KillSwitchScope.GLOBAL,
                key=None,
                reason="database unavailable fixture",
            )
        )
    with pytest.raises(OperationalError, match="control database connection failure"):
        await repository.clear_lock(KillSwitchScope.GLOBAL)

    assert get.await_count == 2
    scalars.assert_not_awaited()

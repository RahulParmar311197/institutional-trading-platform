import os

import pytest

from trading_platform.config import Settings
from trading_platform.infrastructure import Infrastructure

pytestmark = pytest.mark.asyncio


async def test_real_redis_readiness() -> None:
    if os.environ.get("ITP_RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set ITP_RUN_INTEGRATION_TESTS=1 to run Redis integration tests")

    infrastructure = Infrastructure(Settings(_env_file=None))
    try:
        assert await infrastructure.redis_ready() is True
    finally:
        await infrastructure.close()

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from trading_platform.config import Settings


class Infrastructure:
    def __init__(self, settings: Settings) -> None:
        self.db: AsyncEngine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
        )
        self.redis: Redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )

    async def database_ready(self) -> bool:
        try:
            async with self.db.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def redis_ready(self) -> bool:
        try:
            return bool(await self.redis.ping())
        except Exception:
            return False

    async def close(self) -> None:
        await self.redis.aclose()
        await self.db.dispose()


@asynccontextmanager
async def infrastructure_lifespan(settings: Settings) -> AsyncIterator[Infrastructure]:
    infrastructure = Infrastructure(settings)
    try:
        yield infrastructure
    finally:
        await infrastructure.close()
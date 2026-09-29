from enum import StrEnum
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    BACKTEST = "backtest"
    PAPER = "paper"
    STAGING = "staging"
    LIVE = "live"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ITP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "institutional-trading-platform"
    environment: Environment = Environment.LOCAL
    live_trading_enabled: bool = False
    database_url: str = Field(
        default="postgresql+asyncpg://itp:itp@localhost:5432/itp",
        repr=False,
    )
    redis_url: str = Field(default="redis://localhost:6379/0", repr=False)

    @model_validator(mode="after")
    def enforce_live_safety(self) -> "Settings":
        if self.live_trading_enabled and self.environment is not Environment.LIVE:
            raise ValueError("live trading may only be enabled in the LIVE environment")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
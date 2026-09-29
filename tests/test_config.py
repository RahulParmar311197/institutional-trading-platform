import pytest
from pydantic import ValidationError

from trading_platform.config import Environment, Settings


def test_live_trading_is_disabled_by_default() -> None:
    settings = Settings(_env_file=None)
    assert settings.live_trading_enabled is False


def test_live_trading_rejected_outside_live_environment() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment=Environment.PAPER,
            live_trading_enabled=True,
        )


def test_live_environment_does_not_implicitly_enable_trading() -> None:
    settings = Settings(_env_file=None, environment=Environment.LIVE)
    assert settings.live_trading_enabled is False

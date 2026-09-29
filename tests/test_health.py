from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

from trading_platform.app import create_app
from trading_platform.config import Settings


class FakeInfrastructure:
    def __init__(self, *, database: bool, redis: bool) -> None:
        self.database = database
        self.redis = redis

    async def database_ready(self) -> bool:
        return self.database

    async def redis_ready(self) -> bool:
        return self.redis

    async def close(self) -> None:
        return None


def test_liveness_does_not_depend_on_external_services() -> None:
    app = create_app(Settings(_env_file=None))
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_fails_closed_when_dependency_is_unavailable() -> None:
    app = create_app(Settings(_env_file=None))
    fake = FakeInfrastructure(database=True, redis=False)

    @asynccontextmanager
    async def lifespan(_: object) -> AsyncIterator[None]:
        app.state.infrastructure = fake
        yield

    app.router.lifespan_context = lifespan
    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["dependencies"] == {"database": True, "redis": False}

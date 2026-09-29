from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from trading_platform.config import Settings, get_settings
from trading_platform.infrastructure import Infrastructure


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        infrastructure = Infrastructure(app_settings)
        app.state.infrastructure = infrastructure
        try:
            yield
        finally:
            await infrastructure.close()

    app = FastAPI(title=app_settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.settings = app_settings

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def ready(request: Request) -> JSONResponse:
        infrastructure: Infrastructure = request.app.state.infrastructure
        database = await infrastructure.database_ready()
        redis = await infrastructure.redis_ready()
        ready_state = database and redis
        payload: dict[str, Any] = {
            "status": "ready" if ready_state else "not_ready",
            "dependencies": {"database": database, "redis": redis},
            "live_trading_enabled": app_settings.live_trading_enabled,
        }
        return JSONResponse(
            payload,
            status_code=status.HTTP_200_OK
            if ready_state
            else status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return app


app = create_app()
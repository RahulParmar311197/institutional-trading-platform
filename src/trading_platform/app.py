import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from trading_platform.config import Settings, get_settings
from trading_platform.infrastructure import Infrastructure
from trading_platform.logging import configure_logging, get_logger

REQUEST_ID_HEADER = "X-Request-ID"


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging()
    logger = get_logger()

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

    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next: Any) -> Any:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            logger.info(
                "http_request",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
            )
            return response
        finally:
            structlog.contextvars.clear_contextvars()

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
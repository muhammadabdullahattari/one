from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from redis.asyncio import Redis

from src.api.dependencies import set_redis_client
from src.api.middleware import (
    CorrelationIdMiddleware,
    RequestLoggingMiddleware,
    register_exception_handlers,
)
from src.api.routers import (
    analytics_router,
    auth_router,
    dlq_router,
    health_router,
    projects_router,
    queues_router,
    schedules_router,
    tasks_router,
    workers_router,
    ws_router,
)
from src.core.config import get_settings
from src.persistence.session import close_database_engine, get_engine

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()
    logger.info(
        "api_startup_initiating", version=settings.app_version, environment=settings.app_env.value
    )
    get_engine()
    logger.info("database_engine_ready", url=settings.get_sanitized_dict()["database_url"])
    redis_client: Redis | None = None
    try:
        redis_client = Redis.from_url(
            settings.redis_url,
            max_connections=settings.redis_max_connections,
            socket_timeout=settings.redis_socket_timeout,
            decode_responses=True,
        )
        set_redis_client(redis_client)
        logger.info("redis_connection_ready", url=settings.get_sanitized_dict()["redis_url"])
    except Exception as exc:
        logger.warning("redis_connection_failed_at_startup", error=str(exc))
        set_redis_client(None)
    yield
    logger.info("api_shutdown_initiating")
    if redis_client:
        await redis_client.aclose()
        set_redis_client(None)
    await close_database_engine()
    logger.info("api_shutdown_complete")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Task Engine API",
        description="Event-Driven Distributed Task Processing Engine v5.0 API Surface",
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    register_exception_handlers(app)
    api_prefix = "/api/v1"
    app.include_router(health_router, prefix=api_prefix)
    app.include_router(auth_router, prefix=api_prefix)
    app.include_router(projects_router, prefix=api_prefix)
    app.include_router(tasks_router, prefix=api_prefix)
    app.include_router(queues_router, prefix=api_prefix)
    app.include_router(workers_router, prefix=api_prefix)
    app.include_router(schedules_router, prefix=api_prefix)
    app.include_router(dlq_router, prefix=api_prefix)
    app.include_router(analytics_router, prefix=api_prefix)
    app.include_router(ws_router, prefix=api_prefix)

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title="Task Engine API",
            version=settings.app_version,
            description="Event-Driven Distributed Task Processing Engine v5.0 REST API Specification",
            routes=app.routes,
        )
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Provide signed JWT bearer token.",
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "x-api-key",
                "description": "Provide project API key.",
            },
        }
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    object.__setattr__(app, "openapi", custom_openapi)
    return app


app = create_app()

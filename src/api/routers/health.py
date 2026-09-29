import time
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_redis_client
from src.api.schemas.health import ComponentHealth, HealthResponse, ReadinessResponse
from src.core.config import Settings, get_settings
from src.persistence.session import get_db_session

router = APIRouter(prefix="/health", tags=["Health & Readiness"])


@router.get("", response_model=HealthResponse, summary="Liveness probe")
async def liveness_probe(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.app_env.value,
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe validating DB, Redis, and broker connectivity",
)
async def readiness_probe(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis | None, Depends(get_redis_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReadinessResponse:
    components: dict[str, ComponentHealth] = {}
    is_ready = True
    try:
        t0 = time.perf_counter()
        await session.execute(text("SELECT 1"))
        db_latency = round((time.perf_counter() - t0) * 1000, 2)
        components["database"] = ComponentHealth(
            status="healthy",
            latency_ms=db_latency,
            message="PostgreSQL connection pool active and responding",
        )
    except Exception as exc:
        is_ready = False
        components["database"] = ComponentHealth(
            status="unhealthy", latency_ms=None, message=f"Database check failed: {exc}"
        )
    if redis is not None:
        try:
            t0 = time.perf_counter()
            await redis.ping()
            redis_latency = round((time.perf_counter() - t0) * 1000, 2)
            components["redis"] = ComponentHealth(
                status="healthy", latency_ms=redis_latency, message="Redis connected"
            )
        except Exception as exc:
            if settings.is_development or settings.is_test:
                components["redis"] = ComponentHealth(
                    status="degraded",
                    latency_ms=None,
                    message="Redis disconnected (running in standalone/development mode)",
                )
            else:
                is_ready = False
                components["redis"] = ComponentHealth(
                    status="unhealthy", latency_ms=None, message=f"Redis check failed: {exc}"
                )
    else:
        components["redis"] = ComponentHealth(
            status="degraded", latency_ms=None, message="Redis client not initialized"
        )
    readiness_status: Literal["ready", "not_ready"] = "ready" if is_ready else "not_ready"
    if not is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ReadinessResponse(
                status="not_ready", components=components, timestamp=datetime.now(UTC)
            ).model_dump(mode="json"),
        )
    return ReadinessResponse(
        status=readiness_status, components=components, timestamp=datetime.now(UTC)
    )

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ComponentHealth(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ..., description="Subsystem health."
    )
    latency_ms: float | None = Field(
        default=None, ge=0, description="Ping round-trip latency in ms."
    )
    message: str | None = Field(default=None, description="Optional diagnostic message or error.")


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: Literal["ok", "degraded", "down"] = Field(default="ok", description="Process liveness.")
    version: str = Field(default="0.1.0", description="Application version.")
    environment: str = Field(default="development", description="Runtime environment.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Server UTC timestamp."
    )


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: Literal["ready", "not_ready"] = Field(..., description="Overall readiness.")
    components: dict[str, ComponentHealth] = Field(
        default_factory=dict, description="Subsystem component breakdown."
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Server UTC timestamp."
    )

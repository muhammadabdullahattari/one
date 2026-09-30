from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.api.schemas.common import PaginatedResponse


class QueueCreateRequest(BaseModel):
    queue_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern="^[a-zA-Z0-9_\\-\\.]+$",
        description="Unique queue name.",
        examples=["default", "high-priority", "email-notifications"],
    )
    enabled: bool = Field(default=True, description="Whether the queue is accepting tasks.")
    default_priority: int = Field(
        default=5, ge=1, le=10, description="Default priority for tasks in this queue."
    )
    max_concurrency: int = Field(
        default=100, ge=1, le=10000, description="Max concurrent tasks executed from this queue."
    )
    rate_limit_rps: int | None = Field(
        default=None, ge=1, description="Optional token bucket rate limit in requests per second."
    )
    broker_backend: str = Field(
        default="native", description="Broker backend name ('native' or 'redis')."
    )

    @field_validator("broker_backend", mode="before")
    @classmethod
    def normalize_broker_backend(cls, v: object) -> str:
        if isinstance(v, str):
            v_stripped = v.strip()
            if not v_stripped:
                return "native"
            return v_stripped
        return "native" if v is None else str(v)


class QueueUpdateRequest(BaseModel):
    enabled: bool | None = Field(None, description="Toggle queue active state.")
    default_priority: int | None = Field(None, ge=1, le=10, description="Default priority.")
    max_concurrency: int | None = Field(None, ge=1, le=10000, description="Max concurrency.")
    rate_limit_rps: int | None = Field(None, ge=1, description="Rate limit RPS.")
    broker_backend: str | None = Field(
        None,
        description="Broker backend ('native', 'redis', etc.). Omit or leave empty to keep unchanged.",
    )

    @field_validator("broker_backend", mode="before")
    @classmethod
    def normalize_broker_backend(cls, v: object) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            v_stripped = v.strip()
            if not v_stripped:
                return None
            return v_stripped
        return str(v)


class QueueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    queue_name: str = Field(..., description="Unique queue name.")
    enabled: bool = Field(..., description="Active status.")
    default_priority: int = Field(..., description="Default priority.")
    max_concurrency: int = Field(..., description="Concurrency ceiling.")
    rate_limit_rps: int | None = Field(None, description="Rate limit RPS.")
    broker_backend: str = Field(..., description="Underlying broker backend.")
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last updated timestamp.")


class QueueStatsResponse(BaseModel):
    queue_name: str = Field(..., description="Queue name.")
    depth: int = Field(..., ge=0, description="Pending + queued backlog count.")
    oldest_task_age_seconds: float | None = Field(
        None, description="Age in seconds of the oldest pending task."
    )
    active_workers: int = Field(..., ge=0, description="Workers currently serving this queue.")
    running_tasks: int = Field(..., ge=0, description="Currently running tasks in this queue.")
    pending_tasks: int = Field(..., ge=0, description="Tasks waiting in queue.")
    succeeded_24h: int = Field(..., ge=0, description="Completed tasks in last 24 hours.")
    failed_24h: int = Field(..., ge=0, description="Failed tasks in last 24 hours.")


class QueueDepthResponse(BaseModel):
    queue_name: str = Field(..., description="Queue identifier.")
    depth: int = Field(..., ge=0, description="Current queue backlog depth.")
    oldest_task_age_seconds: float | None = Field(
        None, description="Oldest pending task age in seconds."
    )


QueueListResponse = PaginatedResponse[QueueResponse]

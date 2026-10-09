from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.api.schemas.common import PaginatedResponse
from src.core.constants import MisfirePolicy


class ScheduledJobCreateRequest(BaseModel):
    task_type: str = Field(..., min_length=1, max_length=255, description="Registered task type.")
    queue: str = Field(default="default", max_length=100, description="Target queue name.")
    cron: str | None = Field(
        default=None,
        description="Standard 5-field or 6-field cron expression.",
        examples=["0 * * * *", "*/15 * * * * *", "0 0 * * MON-FRI"],
    )
    interval_seconds: int | None = Field(
        default=None, ge=1, le=2592000, description="Fixed interval recurrence in seconds."
    )
    timezone: str = Field(
        default="UTC",
        description="IANA Timezone name (e.g. 'UTC', 'America/New_York', 'Asia/Tokyo').",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Input payload provided to each generated task instance."
    )
    misfire_policy: MisfirePolicy = Field(
        default=MisfirePolicy.COALESCING,
        description="Policy when scheduler misses execution window: skip, catch_up, or coalescing.",
    )
    enabled: bool = Field(
        default=True, description="Whether the schedule is actively generating tasks."
    )
    tenant_id: str | None = Field(
        default=None,
        description="Target tenant ID (restricted to principal's tenant for non-admins).",
    )

    @model_validator(mode="after")
    def validate_recurrence(self) -> ScheduledJobCreateRequest:
        if not self.cron and (not self.interval_seconds):
            raise ValueError("Either 'cron' or 'interval_seconds' must be provided.")
        if self.cron and self.interval_seconds:
            raise ValueError("Specify either 'cron' or 'interval_seconds', not both.")
        return self


class ScheduledJobUpdateRequest(BaseModel):
    cron: str | None = Field(None, description="Updated cron expression.")
    interval_seconds: int | None = Field(None, ge=1, description="Updated interval in seconds.")
    timezone: str | None = Field(None, description="Updated IANA timezone.")
    payload: dict[str, Any] | None = Field(None, description="Updated task input payload.")
    misfire_policy: MisfirePolicy | None = Field(None, description="Updated misfire policy.")
    enabled: bool | None = Field(None, description="Toggle active schedule state.")


class ScheduledJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    schedule_id: UUID = Field(..., description="Unique schedule UUID.")
    tenant_id: str = Field(default="default", description="Associated tenant ID.")
    task_type: str = Field(..., description="Task handler type to trigger.")
    queue: str = Field(..., description="Target queue name.")
    cron: str | None = Field(None, description="Cron expression if defined.")
    interval_seconds: int | None = Field(None, description="Fixed interval if defined.")
    timezone: str = Field(..., description="Configured IANA timezone.")
    misfire_policy: MisfirePolicy = Field(..., description="Active misfire policy.")
    enabled: bool = Field(..., description="Schedule active flag.")
    payload: dict[str, Any] = Field(default_factory=dict, description="Task execution payload.")
    next_run_at: datetime | None = Field(None, description="Next calculated trigger time (UTC).")
    last_run_at: datetime | None = Field(None, description="Previous execution trigger time (UTC).")
    total_run_count: int = Field(default=0, ge=0, description="Total executions spawned.")
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


ScheduledJobListResponse = PaginatedResponse[ScheduledJobResponse]

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.api.schemas.common import PaginatedResponse


class WorkerRegisterRequest(BaseModel):
    worker_id: str = Field(..., min_length=1, max_length=100, description="Unique worker node ID.")
    tenant_id: str = Field(
        default="default", description="Tenant or project identifier for worker isolation."
    )
    hostname: str = Field(..., max_length=255, description="Host machine name / IP.")
    process_id: int = Field(..., description="Operating system PID.")
    version: str = Field(default="0.1.0", description="Worker application version.")
    queues: list[str] = Field(
        default_factory=lambda: ["default"], description="Queues monitored by this worker."
    )
    concurrency: int = Field(default=10, ge=1, le=500, description="Worker task concurrency limit.")
    capabilities: dict[str, Any] = Field(
        default_factory=dict, description="Worker hardware / capability metadata."
    )


class WorkerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    worker_id: str = Field(..., description="Worker identifier.")
    tenant_id: str = Field(default="default", description="Owning tenant identifier.")
    hostname: str = Field(..., description="Host machine.")
    process_id: int = Field(..., description="Process ID.")
    version: str = Field(..., description="Worker version.")
    status: str = Field(..., description="Worker status: 'active', 'draining', 'offline'.")
    queues: list[str] = Field(..., description="Subscribed queues.")
    concurrency: int = Field(..., description="Max concurrency slots.")
    active_task_count: int = Field(
        default=0, ge=0, description="Number of currently executing tasks."
    )
    capabilities: dict[str, Any] = Field(default_factory=dict, description="Worker capabilities.")
    last_heartbeat: datetime = Field(..., description="Most recent heartbeat timestamp (UTC).")
    registered_at: datetime = Field(..., description="Initial registration timestamp (UTC).")
    drained_at: datetime | None = Field(None, description="Drain completion timestamp if offline.")


WorkerListResponse = PaginatedResponse[WorkerResponse]

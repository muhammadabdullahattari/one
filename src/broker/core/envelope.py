from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)
    task_id: UUID
    tenant_id: str = "default"
    task_type: str
    queue: str = "default"
    priority: int = 5
    payload: dict[str, Any] | None = None
    payload_ref: str | None = None
    timeout_seconds: int = 300
    max_attempts: int = 3
    attempt_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    trace_id: str | None = None


class TaskMessage(BaseModel):
    model_config = ConfigDict(frozen=True)
    message_id: str
    queue: str
    envelope: TaskEnvelope
    delivery_count: int = 1
    published_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BrokerStats(BaseModel):
    model_config = ConfigDict(frozen=True)
    backend_name: str
    queue: str
    depth: int = 0
    active_consumers: int = 0
    oldest_task_age_seconds: float = 0.0
    is_healthy: bool = True

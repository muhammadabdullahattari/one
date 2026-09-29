from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.api.schemas.common import PaginatedResponse
from src.core.constants import TaskEventType, TaskStatus


class TaskSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    task_type: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Registered task handler identifier.",
        examples=["process_payment", "send_email", "generate_report"],
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="JSON serializable input parameters for task execution."
    )
    queue: str = Field(
        default="default", min_length=1, max_length=100, description="Target queue name."
    )
    priority: int = Field(
        default=5, ge=1, le=10, description="Task priority where 10 is highest and 1 is lowest."
    )
    max_attempts: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Execution retry limit. If omitted, uses queue/engine default.",
    )
    timeout_seconds: int | None = Field(
        default=None,
        ge=1,
        le=86400,
        description="Execution timeout in seconds. If omitted, uses default.",
    )
    idempotency_key: str | None = Field(
        default=None,
        max_length=255,
        description="Unique caller-provided key to guarantee exactly-once submission semantics.",
    )
    delay_seconds: int | None = Field(
        default=None, ge=0, le=2592000, description="Defer execution by N seconds from submission."
    )
    tenant_id: str | None = Field(
        default=None,
        max_length=100,
        description="Tenant identifier for multi-tenant fairness and quota isolation.",
    )
    metadata: dict[str, Any] | None = Field(
        default=None, description="Optional caller metadata (e.g. trace context, tags)."
    )


class TaskCancelRequest(BaseModel):
    reason: str | None = Field(
        default="User requested cancellation",
        max_length=500,
        description="Reason for cancellation.",
    )


class TaskRetryRequest(BaseModel):
    delay_seconds: int = Field(
        default=0, ge=0, description="Delay before task becomes eligible for execution."
    )
    reset_attempts: bool = Field(default=False, description="If True, resets attempt_count to 0.")


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    task_id: UUID = Field(..., description="Unique task identifier.")
    task_type: str = Field(..., description="Task handler type.")
    queue: str = Field(..., description="Queue name.")
    priority: int = Field(..., description="Task priority (1-10).")
    status: TaskStatus = Field(..., description="Current task state.")
    attempt_count: int = Field(..., description="Number of execution attempts made.")
    max_attempts: int = Field(..., description="Maximum allowed attempts.")
    timeout_seconds: int = Field(..., description="Execution timeout limit in seconds.")
    idempotency_key: str | None = Field(None, description="Idempotency key if submitted.")
    tenant_id: str | None = Field(None, description="Tenant scope.")
    created_at: datetime = Field(..., description="Creation timestamp.")
    scheduled_at: datetime = Field(..., description="Eligible execution timestamp.")
    started_at: datetime | None = Field(None, description="Current or last run start time.")
    finished_at: datetime | None = Field(None, description="Terminal state timestamp.")
    result_ref: str | None = Field(None, description="Reference pointer if result offloaded.")
    error: str | None = Field(None, description="Last error message if failed.")


class TaskDetailResponse(TaskResponse):
    payload: dict[str, Any] = Field(default_factory=dict, description="Task input payload.")
    result: Any | None = Field(None, description="Execution return value (if completed).")
    metadata: dict[str, Any] | None = Field(None, description="Associated task metadata.")
    worker_id: str | None = Field(None, description="Worker currently executing or last owner.")
    lease_expires_at: datetime | None = Field(None, description="Active lease expiration time.")


class TaskAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    attempt_id: UUID = Field(..., description="Attempt UUID.")
    task_id: UUID = Field(..., description="Parent task UUID.")
    attempt_number: int = Field(..., description="1-based attempt sequence number.")
    worker_id: str = Field(..., description="Worker identifier executing the attempt.")
    status: str = Field(..., description="Status of attempt (SUCCEEDED, FAILED, TIMED_OUT).")
    started_at: datetime = Field(..., description="Attempt start timestamp.")
    finished_at: datetime | None = Field(None, description="Attempt completion timestamp.")
    error: str | None = Field(None, description="Error message if attempt failed.")
    duration_ms: float | None = Field(None, description="Execution duration in milliseconds.")


class TaskEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    event_id: UUID = Field(..., description="Event UUID.")
    task_id: UUID = Field(..., description="Associated task UUID.")
    event_type: TaskEventType = Field(..., description="Lifecycle event type.")
    timestamp: datetime = Field(..., description="Event timestamp.")
    worker_id: str | None = Field(None, description="Worker associated with event.")
    details: dict[str, Any] = Field(default_factory=dict, description="Event metadata details.")


TaskListResponse = PaginatedResponse[TaskResponse]

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from src.core.constants import (
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_QUEUE_NAME,
    DEFAULT_TIMEOUT_SECONDS,
    BrokerBackendType,
    MisfirePolicy,
    TaskEventType,
    TaskStatus,
)

VALID_STATE_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.QUEUED, TaskStatus.CANCELLED, TaskStatus.FAILED},
    TaskStatus.SCHEDULED: {TaskStatus.QUEUED, TaskStatus.CANCELLED},
    TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {
        TaskStatus.SUCCEEDED,
        TaskStatus.FAILED,
        TaskStatus.RETRY_WAIT,
        TaskStatus.TIMED_OUT,
        TaskStatus.CANCELLED,
    },
    TaskStatus.RETRY_WAIT: {TaskStatus.QUEUED, TaskStatus.CANCELLED, TaskStatus.DEAD},
    TaskStatus.SUCCEEDED: set(),
    TaskStatus.FAILED: {TaskStatus.RETRY_WAIT, TaskStatus.DEAD},
    TaskStatus.TIMED_OUT: {TaskStatus.RETRY_WAIT, TaskStatus.DEAD},
    TaskStatus.CANCELLED: set(),
    TaskStatus.DEAD: {TaskStatus.QUEUED},
}


class DomainEntity(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, arbitrary_types_allowed=True)


class Task(DomainEntity):
    task_id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(default="default")
    task_type: str
    queue: str = Field(default=DEFAULT_QUEUE_NAME)
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    priority: int = Field(default=5, ge=1, le=10)
    payload: dict[str, Any] | None = Field(default=None)
    payload_ref: str | None = Field(default=None)
    result: dict[str, Any] | None = Field(default=None)
    result_ref: str | None = Field(default=None)
    schedule_id: UUID | None = Field(default=None)
    idempotency_key: str | None = Field(default=None)
    timeout_seconds: int = Field(default=DEFAULT_TIMEOUT_SECONDS, ge=1)
    max_attempts: int = Field(default=DEFAULT_MAX_ATTEMPTS, ge=1)
    attempt_count: int = Field(default=0, ge=0)
    current_worker_id: str | None = Field(default=None)
    lease_expires_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    scheduled_at: datetime | None = Field(default=None)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    version: int = Field(default=1, ge=1)
    status_reason: str | None = Field(default=None)

    def transition_to(self, new_status: TaskStatus, reason: str | None = None) -> None:
        allowed = VALID_STATE_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Illegal task state transition: {self.status.value} -> {new_status.value} is not permitted (SRS §8 Table 6)."
            )
        self.status = new_status
        self.status_reason = reason
        self.version += 1


class TaskAttempt(DomainEntity):
    attempt_id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    worker_id: str
    attempt_number: int = Field(ge=1)
    status: TaskStatus = Field(default=TaskStatus.RUNNING)
    leased_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    lease_expires_at: datetime
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = Field(default=None)
    error_class: str | None = Field(default=None)
    error_message_redacted: str | None = Field(default=None)
    result_ref: str | None = Field(default=None)
    trace_id: str | None = Field(default=None)


class TaskEvent(DomainEntity):
    event_id: UUID = Field(default_factory=uuid4)
    task_id: UUID | None = Field(default=None)
    attempt_id: UUID | None = Field(default=None)
    event_type: TaskEventType
    actor_type: str = Field(default="system")
    actor_id: str = Field(default="engine")
    event_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = Field(default=None)


class TaskOutbox(DomainEntity):
    outbox_id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    event_type: str = Field(default="task.created")
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    published_at: datetime | None = Field(default=None)
    attempts: int = Field(default=0, ge=0)
    last_error: str | None = Field(default=None)
    next_attempt_at: datetime | None = Field(default=None)


class Queue(DomainEntity):
    queue_name: str
    enabled: bool = Field(default=True)
    default_priority: int = Field(default=5, ge=1, le=10)
    max_concurrency: int = Field(default=100, ge=1)
    rate_limit_rps: int = Field(default=100, ge=1)
    retry_defaults: dict[str, Any] = Field(
        default_factory=lambda: {"max_attempts": 3, "backoff": "exponential"}
    )
    retention_days: int = Field(default=30, ge=1)
    broker_backend: str = Field(default="native")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BrokerBackend(DomainEntity):
    backend_name: str
    backend_type: BrokerBackendType = Field(default=BrokerBackendType.NATIVE)
    connection_config_ref: str | None = Field(default=None)
    enabled: bool = Field(default=True)
    status: str = Field(default="healthy")
    last_health_check_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Worker(DomainEntity):
    worker_id: str
    hostname: str
    process_id: int
    version: str = Field(default="0.1.0")
    protocol_version: str = Field(default="1.0")
    capabilities_json: list[str] = Field(default_factory=list)
    queues_json: list[str] = Field(default_factory=lambda: [DEFAULT_QUEUE_NAME])
    concurrency: int = Field(default=10, ge=1)
    active_slots: int = Field(default=0, ge=0)
    status: str = Field(default="active")
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(UTC))
    registered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    drained_at: datetime | None = Field(default=None)


class Schedule(DomainEntity):
    schedule_id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(default="default")
    task_type: str
    queue: str = Field(default=DEFAULT_QUEUE_NAME)
    payload: dict[str, Any] | None = Field(default=None)
    payload_ref: str | None = Field(default=None)
    cron_expression: str | None = Field(default=None)
    interval_seconds: int | None = Field(default=None)
    timezone: str = Field(default="UTC")
    misfire_policy: MisfirePolicy = Field(default=MisfirePolicy.SKIP)
    enabled: bool = Field(default=True)
    next_run_at: datetime | None = Field(default=None)
    last_run_at: datetime | None = Field(default=None)
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IdempotencyKey(DomainEntity):
    scope: str = Field(default="default")
    idempotency_key: str
    task_id: UUID
    request_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime


class DLQEntry(DomainEntity):
    dlq_id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    tenant_id: str = Field(default="default")
    final_attempt_id: UUID | None = Field(default=None)
    reason: str
    error_class: str
    payload_ref: str | None = Field(default=None)
    dead_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    replay_count: int = Field(default=0, ge=0)
    last_replayed_at: datetime | None = Field(default=None)


class ApiCredential(DomainEntity):
    principal_id: UUID = Field(default_factory=uuid4)
    name: str
    role: str = Field(default="producer")
    key_hash: str
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime | None = Field(default=None)


class AuditEvent(DomainEntity):
    audit_id: UUID = Field(default_factory=uuid4)
    actor: str
    action: str
    resource_type: str
    resource_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    outcome: str = Field(default="SUCCESS")
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = Field(default=None)

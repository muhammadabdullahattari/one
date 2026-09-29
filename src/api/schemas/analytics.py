from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ThroughputPoint(BaseModel):
    timestamp: datetime = Field(..., description="Bucket timestamp (UTC).")
    incoming_rate: float = Field(..., ge=0, description="Tasks submitted per second.")
    outgoing_rate: float = Field(..., ge=0, description="Tasks completed/failed per second.")


class ThroughputResponse(BaseModel):
    points: list[ThroughputPoint] = Field(default_factory=list)
    current_incoming_tps: float = Field(default=0.0, ge=0)
    current_outgoing_tps: float = Field(default=0.0, ge=0)


class StatusDistributionItem(BaseModel):
    status: str = Field(..., description="Task status (SUCCEEDED, FAILED, RETRY_WAIT, DEAD, etc.).")
    count: int = Field(..., ge=0, description="Task count in this status.")
    percentage: float = Field(..., ge=0, le=100, description="Share of total tasks.")


class StatusDistributionResponse(BaseModel):
    distribution: list[StatusDistributionItem] = Field(default_factory=list)
    total_tasks: int = Field(..., ge=0)


class LatencyPercentiles(BaseModel):
    p50_ms: float = Field(default=0.0, ge=0, description="50th percentile (median) duration in ms.")
    p95_ms: float = Field(default=0.0, ge=0, description="95th percentile duration in ms.")
    p99_ms: float = Field(default=0.0, ge=0, description="99th percentile duration in ms.")
    avg_ms: float = Field(default=0.0, ge=0, description="Average duration in ms.")


class LatencyResponse(BaseModel):
    queue_wait: LatencyPercentiles
    execution_duration: LatencyPercentiles
    e2e_duration: LatencyPercentiles


class WorkerUtilizationItem(BaseModel):
    worker_id: str
    hostname: str
    active_slots: int = Field(..., ge=0)
    total_concurrency: int = Field(..., ge=1)
    utilization_percent: float = Field(..., ge=0, le=100)
    status: str


class WorkerUtilizationResponse(BaseModel):
    workers: list[WorkerUtilizationItem] = Field(default_factory=list)
    average_utilization_percent: float = Field(default=0.0, ge=0, le=100)


class TaskTypeStatItem(BaseModel):
    task_type: str
    total_count: int = Field(..., ge=0)
    success_count: int = Field(..., ge=0)
    failed_count: int = Field(..., ge=0)
    success_rate: float = Field(..., ge=0, le=100)
    avg_duration_ms: float = Field(default=0.0, ge=0)


class TaskTypeStatsResponse(BaseModel):
    stats: list[TaskTypeStatItem] = Field(default_factory=list)


class QueueDepthPoint(BaseModel):
    queue_name: str
    depth: int = Field(..., ge=0)
    oldest_task_age_seconds: float | None = None
    timestamp: datetime


class QueueDepthTrendResponse(BaseModel):
    queues: list[QueueDepthPoint] = Field(default_factory=list)


class OldestTaskAgeItem(BaseModel):
    queue_name: str
    oldest_task_id: UUID | None = None
    oldest_task_age_seconds: float | None = None
    threshold_warning: bool = False


class OldestTaskAgeResponse(BaseModel):
    queues: list[OldestTaskAgeItem] = Field(default_factory=list)


class BrokerHealthItem(BaseModel):
    backend: str = Field(..., description="Backend name: 'native', 'redis', etc.")
    backend_type: str = Field(default="native")
    connected: bool = True
    status: str = Field(default="healthy")
    active_consumers: int = Field(default=0, ge=0)
    error: str | None = None


class BrokerStatsResponse(BaseModel):
    backend: str
    published_count: int = Field(default=0, ge=0)
    consumed_count: int = Field(default=0, ge=0)
    pending_count: int = Field(default=0, ge=0)
    dead_letter_count: int = Field(default=0, ge=0)

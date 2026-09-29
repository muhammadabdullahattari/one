from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.api.schemas.common import PaginatedResponse


class DLQReplayRequest(BaseModel):
    override_queue: str | None = Field(
        None, max_length=100, description="Optional different queue to target for retry."
    )
    delay_seconds: int = Field(
        default=0, ge=0, description="Delay before replayed task becomes eligible for execution."
    )


class DLQBulkReplayRequest(BaseModel):
    dlq_ids: list[UUID] | None = Field(
        None, description="Specific DLQ entry UUIDs to replay. If omitted, replays by queue filter."
    )
    queue_filter: str | None = Field(None, description="Filter DLQ items by original queue name.")
    max_count: int = Field(
        default=100, ge=1, le=1000, description="Maximum number of entries to replay in this batch."
    )


class DLQEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dlq_id: UUID = Field(..., description="Unique DLQ record identifier.")
    task_id: UUID = Field(..., description="Underlying dead task UUID.")
    final_attempt_id: UUID | None = Field(None, description="Final failed attempt UUID.")
    queue: str = Field(..., description="Original queue name.")
    reason: str = Field(
        ..., description="Cause of dead lettering (MAX_RETRIES_EXCEEDED, FATAL_ERROR)."
    )
    error_class: str | None = Field(None, description="Python exception class name.")
    payload_ref: str | None = Field(None, description="External storage reference if offloaded.")
    dead_at: datetime = Field(..., description="Dead letter insertion timestamp.")
    replay_count: int = Field(default=0, ge=0, description="Number of times replayed.")
    last_replayed_at: datetime | None = Field(None, description="Most recent replay timestamp.")


DLQListResponse = PaginatedResponse[DLQEntryResponse]

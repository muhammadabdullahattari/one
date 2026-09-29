from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")
    code: str = Field(
        ...,
        description="Machine-readable error code (e.g. TASK_NOT_FOUND, INVALID_STATE_TRANSITION).",
    )
    message: str = Field(..., description="Human-readable error explanation.")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured key-value context for debugging and client handling.",
    )
    request_id: str = Field(
        default_factory=lambda: f"req-{uuid4().hex[:12]}",
        description="Correlation request identifier.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="UTC timestamp of error occurrence."
    )


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PaginationParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=1000, description="Page size limit.")
    offset: int = Field(default=0, ge=0, description="Records offset.")


class PaginatedResponse[T](BaseModel):
    model_config = ConfigDict(extra="ignore")
    items: list[T] = Field(..., description="List of items for current page.")
    total: int = Field(..., ge=0, description="Total matching records count.")
    limit: int = Field(..., ge=1, description="Requested limit.")
    offset: int = Field(..., ge=0, description="Requested offset.")
    has_more: bool = Field(..., description="Whether additional records exist beyond this page.")

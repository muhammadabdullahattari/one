from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.persistence.models.base import Base, TimestampMixin


class ScheduleModel(Base, TimestampMixin):
    __tablename__ = "schedules"
    schedule_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), default="default", nullable=False, index=True
    )
    task_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    queue: Mapped[str] = mapped_column(String(128), default="default", nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    payload_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cron_expression: Mapped[str | None] = mapped_column(String(64), nullable=True)
    interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    misfire_policy: Mapped[str] = mapped_column(String(32), default="skip", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (
        Index("ix_schedules_due", "enabled", "next_run_at"),
        Index("ix_schedules_tenant_due", "tenant_id", "enabled", "next_run_at"),
    )

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.persistence.models.base import Base, TimestampMixin


class TaskModel(Base, TimestampMixin):
    __tablename__ = "tasks"
    task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(
        String(64), default="default", nullable=False, index=True
    )
    task_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    queue: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("queues.queue_name", ondelete="RESTRICT"),
        default="default",
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False, index=True)
    priority: Mapped[int] = mapped_column(SmallInteger, default=5, nullable=False, index=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    payload_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    result_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    schedule_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("schedules.schedule_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_worker_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    attempts = relationship(
        "TaskAttemptModel",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskAttemptModel.attempt_number",
    )
    events = relationship("TaskEventModel", back_populates="task", cascade="all, delete-orphan")
    __table_args__ = (
        Index("ix_tasks_claim", "queue", "status", "priority", "created_at"),
        Index("ix_tasks_tenant_idempotency", "tenant_id", "idempotency_key"),
        Index(
            "ix_tasks_pending_hotpath",
            "queue",
            "created_at",
            postgresql_where=text("status = 'PENDING'"),
        ),
        Index(
            "ix_tasks_running_lease_expiry",
            "lease_expires_at",
            postgresql_where=text("status = 'RUNNING'"),
        ),
    )

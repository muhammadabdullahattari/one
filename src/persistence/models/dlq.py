from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.persistence.models.base import Base


class DLQEntryModel(Base):
    __tablename__ = "dlq_entries"
    dlq_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    final_attempt_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    error_class: Mapped[str] = mapped_column(String(256), nullable=False)
    payload_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    dead_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    replay_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_replayed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

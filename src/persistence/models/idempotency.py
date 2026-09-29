from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.persistence.models.base import Base


class IdempotencyKeyModel(Base):
    __tablename__ = "idempotency_keys"
    scope: Mapped[str] = mapped_column(String(64), primary_key=True, default="default")
    idempotency_key: Mapped[str] = mapped_column(String(256), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False
    )
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    __table_args__ = (
        UniqueConstraint("scope", "idempotency_key", name="uq_scope_idempotency_key"),
        Index("ix_idempotency_expires", "expires_at"),
    )

from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.persistence.models.base import Base, TimestampMixin


class QueueModel(Base, TimestampMixin):
    __tablename__ = "queues"
    queue_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), default="default", nullable=False, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_priority: Mapped[int] = mapped_column(SmallInteger, default=5, nullable=False)
    max_concurrency: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    rate_limit_rps: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    retry_defaults: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    broker_backend: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("broker_backends.backend_name", ondelete="RESTRICT"),
        default="native",
        nullable=False,
    )
    __table_args__ = (Index("ix_queues_tenant_name", "tenant_id", "queue_name"),)

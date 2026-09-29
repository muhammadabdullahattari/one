from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.persistence.models.base import Base


class WorkerModel(Base):
    __tablename__ = "workers"
    worker_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    hostname: Mapped[str] = mapped_column(String(256), nullable=False)
    process_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="0.1.0", nullable=False)
    protocol_version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    capabilities_json: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    queues_json: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    concurrency: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    active_slots: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    last_heartbeat: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    drained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

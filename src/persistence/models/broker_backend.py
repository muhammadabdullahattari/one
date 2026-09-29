from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.persistence.models.base import Base, TimestampMixin


class BrokerBackendModel(Base, TimestampMixin):
    __tablename__ = "broker_backends"
    backend_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    backend_type: Mapped[str] = mapped_column(String(32), nullable=False)
    connection_config_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="healthy", nullable=False)
    last_health_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

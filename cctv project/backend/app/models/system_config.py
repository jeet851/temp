"""
VisionGuard — System Configuration ORM Model.

Singleton-row pattern storing application thresholds,
capture intervals, retention policies, and version info.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Integer, Float, String, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SystemConfig(Base):
    """Global system configuration (singleton row)."""

    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    temp_warning: Mapped[float] = mapped_column(Float, nullable=False, default=28.0)
    temp_critical: Mapped[float] = mapped_column(Float, nullable=False, default=32.0)
    hum_warning: Mapped[float] = mapped_column(Float, nullable=False, default=65.0)
    hum_critical: Mapped[float] = mapped_column(Float, nullable=False, default=75.0)
    capture_interval: Mapped[int] = mapped_column(
        Integer, nullable=False, default=300
    )  # seconds
    ocr_polling_interval_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=300
    )
    allow_synthetic_fallback: Mapped[bool] = mapped_column(
        nullable=False, default=True
    )
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    system_version: Mapped[str] = mapped_column(
        String(20), nullable=True, default="2.0.0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("users.id"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SystemConfig v{self.system_version}>"

"""
VisionGuard — Environmental History ORM Model.

Stores hourly compliance snapshots including temperature,
humidity, smoke/fire detection flags, and AI risk level.
These are the primary audit trail records.
"""

from datetime import datetime, timezone

from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class EnvironmentalHistory(Base):
    """Hourly environmental compliance snapshot."""

    __tablename__ = "environmental_history"
    __table_args__ = (
        Index("idx_history_room_ts", "room_id", "timestamp"),
        Index("idx_history_risk", "risk_level"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    room_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rooms.id"), nullable=False
    )
    camera_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cameras.id"), nullable=False
    )
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    humidity: Mapped[float] = mapped_column(Float, nullable=False)
    smoke_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fire_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    risk_level: Mapped[str] = mapped_column(
        String(10), nullable=False, default="low"
    )  # low | medium | high
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<History {self.id}: {self.temperature}°C, risk={self.risk_level}>"

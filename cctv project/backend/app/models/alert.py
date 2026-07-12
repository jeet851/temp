"""
VisionGuard — Alert ORM Model.

Stores threshold violation alerts with lifecycle tracking:
active → acknowledged → resolved.
"""

from datetime import datetime, timezone

from sqlalchemy import String, Float, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Alert(Base):
    """Environmental threshold violation alert."""

    __tablename__ = "alerts"
    __table_args__ = (
        Index("idx_alerts_room_status", "room_id", "status"),
        Index("idx_alerts_severity", "severity"),
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
    type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # temperature | humidity
    value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # warning | critical
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active | acknowledged | resolved
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Alert {self.id}: {self.type} {self.severity} ({self.status})>"

"""
VisionGuard — Camera ORM Model.

Represents a CCTV / IP camera device linked to a room.
"""

from datetime import datetime, timezone

from sqlalchemy import String, Float, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Camera(Base):
    """CCTV camera device."""

    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    room_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rooms.id"), nullable=False, index=True
    )
    rtsp_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="online"
    )  # online | offline
    fps: Mapped[float] = mapped_column(Float, nullable=False, default=15.0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    ocr_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=96.0)
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
        return f"<Camera {self.id}: {self.name}>"

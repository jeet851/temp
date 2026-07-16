"""
VisionGuard — Environmental Reading ORM Model.

Stores live telemetry readings captured every few seconds
by the OCR pipeline. The frontend uses these for real-time
gauge displays and trend charts.
"""

from datetime import datetime, timezone

from sqlalchemy import String, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class EnvironmentalReading(Base):
    """Real-time environmental sensor reading."""

    __tablename__ = "environmental_readings"
    __table_args__ = (
        Index("idx_readings_room_ts", "room_id", "timestamp"),
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
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="normal"
    )  # normal | warning | critical
    is_synthetic: Mapped[bool] = mapped_column(
        nullable=False, default=False
    )  # True when values were randomly generated (fallback), False for real OCR reads
    ocr_source: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # "rtsp" | "upload" | "synthetic" | "test" — matches OcrResult.source
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Reading {self.id}: {self.temperature}°C / {self.humidity}%>"

from datetime import datetime
from pydantic import BaseModel, Field


class EnvironmentalReadingBase(BaseModel):
    """Common fields for telemetry."""

    room_id: str
    camera_id: str
    temperature: float
    humidity: float
    ocr_confidence: float | None = None
    status: str = "normal"  # normal | warning | critical


class EnvironmentalReadingCreate(EnvironmentalReadingBase):
    """Payload to post new live OCR detection telemetry."""

    pass


class EnvironmentalReadingRead(EnvironmentalReadingBase):
    """Reading representation for API responses."""

    id: str
    timestamp: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class EnvironmentalHistoryRead(BaseModel):
    """Hourly environmental snapshot audit record representation."""

    id: str
    timestamp: datetime
    room_id: str
    camera_id: str
    temperature: float
    humidity: float
    smoke_detected: bool
    fire_detected: bool
    risk_level: str  # low | medium | high
    image_path: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ManualCaptureRequest(BaseModel):
    """Payload to manually trigger a snapshot record entry."""

    room_id: str
    temperature: float
    humidity: float

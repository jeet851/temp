from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_serializer


def _to_utc_z(v: datetime) -> str:
    """Serialize a datetime as ISO 8601 with explicit 'Z' UTC suffix.

    SQLite returns naive datetimes from the DB. We always store UTC, so we
    attach the UTC timezone before formatting so the browser receives a
    properly-tagged timestamp it can convert to local IST automatically.
    """
    if v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)
    return v.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'


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
    is_synthetic: bool = False   # True = randomly generated fallback, False = real OCR
    ocr_source: str | None = None  # "rtsp" | "upload" | "synthetic" | "test"
    created_at: datetime

    @field_serializer('timestamp', 'created_at')
    def serialize_dt(self, v: datetime) -> str:
        return _to_utc_z(v)

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
    is_synthetic: bool = False   # True = synthetic fallback, False = real OCR
    ocr_source: str | None = None  # "rtsp" | "upload" | "synthetic" | "test"
    created_at: datetime

    @field_serializer('timestamp', 'created_at')
    def serialize_dt(self, v: datetime) -> str:
        return _to_utc_z(v)

    class Config:
        from_attributes = True


class ManualCaptureRequest(BaseModel):
    """Payload to manually trigger a snapshot record entry."""

    room_id: str
    temperature: float
    humidity: float

from datetime import datetime, timezone
from pydantic import BaseModel, field_serializer


def _to_utc_z(v: datetime | None) -> str | None:
    if v is None:
        return None
    if v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)
    return v.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'


class CameraRead(BaseModel):
    """Camera device details serialization model."""

    id: str
    name: str
    room_id: str
    rtsp_url: str | None = None
    status: str  # online | offline
    fps: float
    latency_ms: int
    ocr_confidence: float
    last_seen_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @field_serializer('created_at', 'updated_at', 'last_seen_at')
    def serialize_dt(self, v: datetime | None) -> str | None:
        return _to_utc_z(v)

    class Config:
        from_attributes = True

from datetime import datetime
from pydantic import BaseModel


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
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

from datetime import datetime
from pydantic import BaseModel, Field


class AlertBase(BaseModel):
    """Common fields for alerts management."""

    room_id: str
    camera_id: str
    type: str  # temperature | humidity
    value: float
    threshold: float
    severity: str  # warning | critical
    status: str = "active"  # active | acknowledged | resolved
    image_url: str | None = None


class AlertCreate(AlertBase):
    """Payload to raise a new alert."""

    pass


class AlertAcknowledge(BaseModel):
    """Payload to acknowledge an active alert."""

    operator: str = Field(..., max_length=255)


class AlertResolve(BaseModel):
    """Payload to resolve an alert."""

    operator: str = Field(..., max_length=255)
    resolution_notes: str = Field(..., min_length=5)


class AlertRead(AlertBase):
    """Serialized alert log entry representation."""

    id: str
    timestamp: datetime
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    resolution_notes: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

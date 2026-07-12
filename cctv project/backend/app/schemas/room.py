from datetime import datetime
from pydantic import BaseModel


class RoomRead(BaseModel):
    """Room details serialization model."""

    id: str
    name: str
    location: str
    status: str  # normal | warning | critical
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

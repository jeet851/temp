from pydantic import BaseModel
from app.schemas.alert import AlertRead
from app.schemas.environment import EnvironmentalHistoryRead


class DashboardSummary(BaseModel):
    """Aggregated status, alerts, and capture history for the main Dashboard view."""

    current_temperature: float | None = None
    current_humidity: float | None = None
    smoke_status: bool
    fire_status: bool
    risk_level: str  # low | medium | high
    system_status: str  # normal | warning | critical
    today_alerts_count: int
    today_captures_count: int
    recent_alerts: list[AlertRead]
    recent_captures: list[EnvironmentalHistoryRead]
    ocr_confidence: float | None = None

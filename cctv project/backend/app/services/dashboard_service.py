from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.dashboard import DashboardSummary
from app.repositories.environment_repo import EnvironmentRepository
from app.repositories.alert_repo import AlertRepository
from app.repositories.room_repo import RoomRepository


class DashboardService:
    """Computes aggregated dashboard metrics and summary stats."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.env_repo = EnvironmentRepository(db)
        self.alert_repo = AlertRepository(db)
        self.room_repo = RoomRepository(db)

    async def get_summary(self, room_id: str) -> DashboardSummary:
        """Fetch and aggregate summary metrics for the given room."""
        # Current Reading
        latest_reading = await self.env_repo.get_latest_reading(room_id)
        
        # Fallback values if no reading yet
        temp = latest_reading.temperature if latest_reading else 22.5
        hum = latest_reading.humidity if latest_reading else 48.0
        status = latest_reading.status if latest_reading else "normal"
        conf = latest_reading.ocr_confidence if latest_reading else 98.2

        # Room details
        room = await self.room_repo.get_by_id(room_id)
        system_status = room.status if room else status

        # Smoke/Fire flags from last history point or alert
        smoke = False
        fire = False
        risk = "low"
        
        # Load latest history record for flags
        history_list, _ = await self.env_repo.list_history(room_id=room_id, page=1, per_page=1)
        if history_list:
            latest_history = history_list[0]
            smoke = latest_history.smoke_detected
            fire = latest_history.fire_detected
            risk = latest_history.risk_level

        # Active Alerts
        active_alerts = await self.alert_repo.list_all(room_id=room_id, status="active")
        
        # Today's capture counts (past 24h)
        day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        _, total_history_24h = await self.env_repo.list_history(room_id=room_id, start_date=day_ago)

        # Recent activities
        recent_captures, _ = await self.env_repo.list_history(room_id=room_id, page=1, per_page=5)

        return DashboardSummary(
            current_temperature=temp,
            current_humidity=hum,
            smoke_status=smoke,
            fire_status=fire,
            risk_level=risk,
            system_status=system_status,
            today_alerts_count=len(active_alerts),
            today_captures_count=total_history_24h,
            recent_alerts=active_alerts,
            recent_captures=recent_captures,
            ocr_confidence=conf
        )

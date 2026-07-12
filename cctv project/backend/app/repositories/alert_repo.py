from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert


class AlertRepository:
    """Handles database queries for environmental violation Alerts."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, alert_id: str) -> Alert | None:
        """Fetch a single alert by ID."""
        result = await self.db.execute(select(Alert).where(Alert.id == alert_id))
        return result.scalar_one_or_none()

    async def list_all(
        self,
        room_id: str | None = None,
        status: str | None = None,
        severity: str | None = None,
    ) -> list[Alert]:
        """Fetch all alerts, optionally filtered by room, status, and severity."""
        query = select(Alert).order_by(Alert.timestamp.desc())
        filters = []

        if room_id:
            filters.append(Alert.room_id == room_id)
        if status:
            filters.append(Alert.status == status)
        if severity:
            filters.append(Alert.severity == severity)

        if filters:
            query = query.where(and_(*filters))

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(self, alert: Alert) -> Alert:
        """Create a new alert record."""
        self.db.add(alert)
        await self.db.flush()
        return alert

    async def update(self, alert: Alert) -> Alert:
        """Persist updates to an alert instance."""
        self.db.add(alert)
        await self.db.flush()
        return alert

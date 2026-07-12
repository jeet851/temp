from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.repositories.alert_repo import AlertRepository
from app.repositories.room_repo import RoomRepository
from app.websocket.manager import ws_manager


class AlertService:
    """Manages active alarms logs, operator lifecycle states, and broadcasts."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.alert_repo = AlertRepository(db)
        self.room_repo = RoomRepository(db)

    async def get_alerts(
        self,
        room_id: str | None = None,
        status_val: str | None = None,
        severity: str | None = None,
    ) -> list[Alert]:
        """Fetch alert logs from database."""
        return await self.alert_repo.list_all(room_id, status_val, severity)

    async def acknowledge_alert(self, alert_id: str, operator: str) -> Alert:
        """Acknowledge an active alert and broadcast state changes."""
        alert = await self.alert_repo.get_by_id(alert_id)
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert record not found."
            )

        if alert.status != "active":
            return alert  # Already acknowledged/resolved

        alert.status = "acknowledged"
        alert.acknowledged_by = operator
        alert.acknowledged_at = datetime.now(timezone.utc)
        
        await self.alert_repo.update(alert)
        await self._broadcast_alerts_changed()
        return alert

    async def resolve_alert(self, alert_id: str, operator: str, resolution_notes: str) -> Alert:
        """Resolve a violation alert and recalculate room severity status."""
        alert = await self.alert_repo.get_by_id(alert_id)
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert record not found."
            )

        alert.status = "resolved"
        alert.resolved_by = operator
        alert.resolved_at = datetime.now(timezone.utc)
        alert.resolution_notes = resolution_notes

        await self.alert_repo.update(alert)

        # Recalculate room severity status
        room = await self.room_repo.get_by_id(alert.room_id)
        if room:
            active_alerts = await self.alert_repo.list_all(room_id=room.id, status="active")
            room_status = "normal"
            if any(a.severity == "critical" for a in active_alerts):
                room_status = "critical"
            elif any(a.severity == "warning" for a in active_alerts):
                room_status = "warning"

            if room.status != room_status:
                room.status = room_status
                await self.room_repo.update(room)
                all_rooms = await self.room_repo.list_all()
                await ws_manager.broadcast("rooms", [
                    {"id": r.id, "name": r.name, "location": r.location, "status": r.status}
                    for r in all_rooms
                ])

        await self._broadcast_alerts_changed()
        return alert

    async def _broadcast_alerts_changed(self) -> None:
        """Push updated alerts lists via WS."""
        all_alerts = await self.alert_repo.list_all()
        await ws_manager.broadcast("alertsChanged", [
            {
                "id": a.id,
                "timestamp": a.timestamp.isoformat(),
                "roomId": a.room_id,
                "cameraId": a.camera_id,
                "type": a.type,
                "value": a.value,
                "threshold": a.threshold,
                "severity": a.severity,
                "status": a.status,
                "imageUrl": a.image_url,
                "acknowledgedBy": a.acknowledged_by,
                "acknowledgedAt": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
                "resolvedBy": a.resolved_by,
                "resolvedAt": a.resolved_at.isoformat() if a.resolved_at else None,
                "resolutionNotes": a.resolution_notes
            } for a in all_alerts
        ])

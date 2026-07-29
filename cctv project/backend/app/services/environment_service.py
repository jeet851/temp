import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession


def _fmt_utc(dt: datetime) -> str:
    """Format a datetime as ISO 8601 with explicit UTC 'Z' suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'

from app.models.environmental_reading import EnvironmentalReading
from app.models.environmental_history import EnvironmentalHistory
from app.repositories.environment_repo import EnvironmentRepository
from app.repositories.room_repo import RoomRepository
from app.repositories.camera_repo import CameraRepository
from app.repositories.settings_repo import SettingsRepository
from app.repositories.alert_repo import AlertRepository
from app.models.alert import Alert
from app.websocket.manager import ws_manager
from app.utils.helpers import generate_id


class EnvironmentService:
    """Manages business operations for environmental readings, history, and actions."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.env_repo = EnvironmentRepository(db)
        self.room_repo = RoomRepository(db)
        self.camera_repo = CameraRepository(db)
        self.settings_repo = SettingsRepository(db)
        self.alert_repo = AlertRepository(db)

    async def get_rooms(self) -> list:
        """Fetch all room zones."""
        return await self.room_repo.list_all()

    async def get_readings(self, room_id: str | None = None, limit: int = 50) -> list:
        """Fetch recent telemetry readings."""
        return await self.env_repo.list_recent_readings(room_id, limit)

    async def get_history(
        self,
        room_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        risk_level: str | None = None,
        search_query: str | None = None,
        page: int = 1,
        per_page: int = 10,
    ) -> tuple[list, int]:
        """Fetch a paginated list of historical records."""
        return await self.env_repo.list_history(
            room_id, start_date, end_date, risk_level, search_query, page, per_page
        )

    async def broadcast_live_telemetry(
        self,
        room_id: str,
        temp: float,
        hum: float,
        ocr_confidence: float = 0.0,
        ocr_source: str = "live",
        low_confidence: bool = False,
    ) -> None:
        """
        Broadcast live monitoring telemetry to Dashboard and OCR Extraction UI
        WITHOUT persisting a record into environmental_history.
        """
        now = datetime.now(timezone.utc)
        config = await self.settings_repo.get_config()

        status = "normal"
        if temp >= config.temp_critical or hum >= config.hum_critical:
            status = "critical"
        elif temp >= config.temp_warning or hum >= config.hum_warning:
            status = "warning"

        is_synthetic = ocr_source in ("synthetic", "test")

        await ws_manager.broadcast("reading", {
            "id": generate_id("r"),
            "timestamp": _fmt_utc(now),
            "roomId": room_id,
            "cameraId": "camera-001",
            "temperature": temp,
            "humidity": hum,
            "ocrConfidence": ocr_confidence,
            "status": status,
            "isSynthetic": is_synthetic,
            "ocrSource": ocr_source,
            "lowConfidence": low_confidence,
        })

    async def trigger_manual_capture(
        self,
        room_id: str,
        temp: float,
        hum: float,
        ocr_confidence: float = 0.0,
        ocr_source: str = "live",
        image_saved_path: str | None = None,
        low_confidence: bool = False,
    ) -> EnvironmentalHistory:
        """
        Trigger an OCR capture and persist the results.
        """
        final_image_path = None
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Room not found.")

        # Find camera in the room
        cameras = await self.camera_repo.list_by_room(room_id)
        camera = cameras[0] if cameras else None
        if not camera:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="No camera configured for this room.")

        # Load thresholds
        config = await self.settings_repo.get_config()

        # Check status
        status = "normal"
        if temp >= config.temp_critical or hum >= config.hum_critical:
            status = "critical"
        elif temp >= config.temp_warning or hum >= config.hum_warning:
            status = "warning"

        # Determine whether this is a synthetic (fallback) reading
        is_synthetic = ocr_source in ("synthetic", "test")

        # Create Reading
        now = datetime.now(timezone.utc)
        reading = EnvironmentalReading(
            id=generate_id("r"),
            timestamp=now,
            room_id=room_id,
            camera_id=camera.id,
            temperature=temp,
            humidity=hum,
            ocr_confidence=ocr_confidence,   # ✅ Fixed M-01: real value, not hardcoded 99
            status=status,
            is_synthetic=is_synthetic,
            ocr_source=ocr_source,
            low_confidence=low_confidence,
        )
        await self.env_repo.create_reading(reading)
        await self.db.commit()
        await self.db.refresh(reading)
        await ws_manager.broadcast("reading", {
            "id": reading.id,
            "timestamp": _fmt_utc(reading.timestamp),
            "roomId": reading.room_id,
            "cameraId": reading.camera_id,
            "temperature": reading.temperature,
            "humidity": reading.humidity,
            "ocrConfidence": reading.ocr_confidence,
            "status": reading.status,
            "isSynthetic": reading.is_synthetic,   # ✅ Step 4c: exposed to frontend
            "ocrSource": reading.ocr_source,
            "lowConfidence": reading.low_confidence,
        })

        # Process alerts if not normal
        if status != "normal":
            type_val = "temperature" if temp >= config.temp_warning else "humidity"
            limit_val = temp if type_val == "temperature" else hum
            threshold_val = (
                (config.temp_critical if status == "critical" else config.temp_warning)
                if type_val == "temperature"
                else (config.hum_critical if status == "critical" else config.hum_warning)
            )

            # Check if active alert already exists
            active_alerts = await self.alert_repo.list_all(room_id=room_id, status="active")
            has_active = any(a.type == type_val for a in active_alerts)

            if not has_active:
                alert = Alert(
                    id=generate_id("alt"),
                    timestamp=now,
                    room_id=room_id,
                    camera_id=camera.id,
                    type=type_val,
                    value=limit_val,
                    threshold=threshold_val,
                    severity=status,
                    status="active",
                    image_url="crop_manual.jpg"
                )
                await self.alert_repo.create(alert)
                
                # Broadcast alert events
                await ws_manager.broadcast("alert", {
                    "alert": {
                        "id": alert.id,
                        "timestamp": _fmt_utc(alert.timestamp),
                        "roomId": alert.room_id,
                        "cameraId": alert.camera_id,
                        "type": alert.type,
                        "value": alert.value,
                        "threshold": alert.threshold,
                        "severity": alert.severity,
                        "status": alert.status,
                        "imageUrl": alert.image_url
                    },
                    "roomName": room.name
                })
                
                # Update alert count notifications list
                all_alerts = await self.alert_repo.list_all()
                await ws_manager.broadcast("alertsChanged", [
                    {
                        "id": a.id,
                        "timestamp": _fmt_utc(a.timestamp),
                        "roomId": a.room_id,
                        "cameraId": a.camera_id,
                        "type": a.type,
                        "value": a.value,
                        "threshold": a.threshold,
                        "severity": a.severity,
                        "status": a.status,
                        "imageUrl": a.image_url,
                        "acknowledgedBy": a.acknowledged_by,
                        "acknowledgedAt": _fmt_utc(a.acknowledged_at) if a.acknowledged_at else None
                    } for a in all_alerts
                ])

        # Recalculate room severity status based on active alerts
        active_room_alerts = await self.alert_repo.list_all(room_id=room_id, status="active")
        room_status = "normal"
        if any(a.severity == "critical" for a in active_room_alerts):
            room_status = "critical"
        elif any(a.severity == "warning" for a in active_room_alerts):
            room_status = "warning"

        if room.status != room_status:
            room.status = room_status
            await self.room_repo.update(room)
            await self.db.commit()
            all_rooms = await self.room_repo.list_all()
            await ws_manager.broadcast("rooms", [
                {"id": r.id, "name": r.name, "location": r.location, "status": r.status}
                for r in all_rooms
            ])

        # Create History
        smoke = False
        fire = False
        risk = "low"
        if status == "critical":
            risk = "high"
        elif status == "warning":
            risk = "medium"

        history = EnvironmentalHistory(
            id=generate_id("h"),
            timestamp=now,
            room_id=room_id,
            camera_id=camera.id,
            temperature=temp,
            humidity=hum,
            smoke_detected=smoke,
            fire_detected=fire,
            risk_level=risk,
            image_path=image_saved_path,          # ✅ Fixed m-07: real annotated snapshot path
            is_synthetic=is_synthetic,
            ocr_source=ocr_source,
            low_confidence=low_confidence,
        )
        await self.env_repo.create_history(history)
        await self.db.commit()
        await self.db.refresh(history)

        # Broadcast history update
        all_history, _ = await self.env_repo.list_history(page=1, per_page=100)
        await ws_manager.broadcast("historyChanged", [
            {
                "id": h.id,
                "timestamp": _fmt_utc(h.timestamp),
                "roomId": h.room_id,
                "cameraId": h.camera_id,
                "temperature": h.temperature,
                "humidity": h.humidity,
                "smokeDetected": h.smoke_detected,
                "fireDetected": h.fire_detected,
                "riskLevel": h.risk_level,
                "imagePath": h.image_path,
                "isSynthetic": h.is_synthetic,    # ✅ Step 4c: exposed to frontend
                "ocrSource": h.ocr_source,
                "lowConfidence": h.low_confidence,
            } for h in all_history
        ])

        return history

    async def trigger_camera_offline_alert(self, room_id: str, camera_id: str) -> None:
        """Raise an alert when a camera goes offline."""
        now = datetime.now(timezone.utc)
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            return
            
        # Check if active alert of type 'camera_offline' already exists
        active_alerts = await self.alert_repo.list_all(room_id=room_id, status="active")
        has_active = any(a.type == "camera_offline" for a in active_alerts)
        
        if not has_active:
            alert = Alert(
                id=generate_id("alt"),
                timestamp=now,
                room_id=room_id,
                camera_id=camera_id,
                type="camera_offline",
                value=0.0,
                threshold=1.0,
                severity="critical",
                status="active",
                image_url="camera_offline.jpg"
            )
            await self.alert_repo.create(alert)
            await self.db.commit()
            
            # Broadcast alert to all connected clients
            await ws_manager.broadcast("alert", {
                "alert": {
                    "id": alert.id,
                    "timestamp": _fmt_utc(alert.timestamp),
                    "roomId": alert.room_id,
                    "cameraId": alert.camera_id,
                    "type": alert.type,
                    "value": alert.value,
                    "threshold": alert.threshold,
                    "severity": alert.severity,
                    "status": alert.status,
                    "imageUrl": alert.image_url
                },
                "roomName": room.name
            })
            
            # Broadcast update to the global alerts list
            all_alerts = await self.alert_repo.list_all()
            await ws_manager.broadcast("alertsChanged", [
                {
                    "id": a.id,
                    "timestamp": _fmt_utc(a.timestamp),
                    "roomId": a.room_id,
                    "cameraId": a.camera_id,
                    "type": a.type,
                    "value": a.value,
                    "threshold": a.threshold,
                    "severity": a.severity,
                    "status": a.status,
                    "imageUrl": a.image_url,
                    "acknowledgedBy": a.acknowledged_by,
                    "acknowledgedAt": _fmt_utc(a.acknowledged_at) if a.acknowledged_at else None
                } for a in all_alerts
            ])
            
            # Update room status to critical if it's not already critical
            if room.status != "critical":
                room.status = "critical"
                await self.room_repo.update(room)
                await self.db.commit()
                all_rooms = await self.room_repo.list_all()
                await ws_manager.broadcast("rooms", [
                    {"id": r.id, "name": r.name, "location": r.location, "status": r.status}
                    for r in all_rooms
                ])

    async def resolve_camera_offline_alerts(self, room_id: str) -> None:
        """Automatically resolve active 'camera_offline' alerts when the camera reconnects."""
        active_alerts = await self.alert_repo.list_all(room_id=room_id, status="active")
        offline_alerts = [a for a in active_alerts if a.type == "camera_offline"]
        
        if not offline_alerts:
            return
            
        now = datetime.now(timezone.utc)
        for alert in offline_alerts:
            alert.status = "resolved"
            alert.resolved_by = "system"
            alert.resolved_at = now
            alert.resolution_notes = "Camera connection restored."
            await self.alert_repo.update(alert)
            
        await self.db.commit()
        
        # Recalculate room severity status
        room = await self.room_repo.get_by_id(room_id)
        if room:
            remaining_active = await self.alert_repo.list_all(room_id=room_id, status="active")
            room_status = "normal"
            if any(a.severity == "critical" for a in remaining_active):
                room_status = "critical"
            elif any(a.severity == "warning" for a in remaining_active):
                room_status = "warning"
                
            if room.status != room_status:
                room.status = room_status
                await self.room_repo.update(room)
                await self.db.commit()
                all_rooms = await self.room_repo.list_all()
                await ws_manager.broadcast("rooms", [
                    {"id": r.id, "name": r.name, "location": r.location, "status": r.status}
                    for r in all_rooms
                ])
                
        # Broadcast update to the global alerts list
        all_alerts = await self.alert_repo.list_all()
        await ws_manager.broadcast("alertsChanged", [
            {
                "id": a.id,
                "timestamp": _fmt_utc(a.timestamp),
                "roomId": a.room_id,
                "cameraId": a.camera_id,
                "type": a.type,
                "value": a.value,
                "threshold": a.threshold,
                "severity": a.severity,
                "status": a.status,
                "imageUrl": a.image_url,
                "acknowledgedBy": a.acknowledged_by,
                "acknowledgedAt": _fmt_utc(a.acknowledged_at) if a.acknowledged_at else None,
                "resolvedBy": a.resolved_by,
                "resolvedAt": _fmt_utc(a.resolved_at) if a.resolved_at else None,
                "resolutionNotes": a.resolution_notes
            } for a in all_alerts
        ])

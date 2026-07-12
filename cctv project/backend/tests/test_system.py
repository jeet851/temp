import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch

from app.models.environmental_reading import EnvironmentalReading
from app.models.environmental_history import EnvironmentalHistory
from app.models.alert import Alert
from app.models.room import Room
from app.schemas.ocr import OcrResult, OcrDigitResult

# Create a deterministic mock OcrResult to avoid random fallback issues
mock_ocr_result = OcrResult(
    temperature=24.5,
    humidity=58.2,
    ocr_confidence=98.0,
    temp_detail=OcrDigitResult(
        raw_text="24.5",
        value=24.5,
        confidence=0.98,
        roi=[43, 58, 110, 48]
    ),
    hum_detail=OcrDigitResult(
        raw_text="58.2",
        value=58.2,
        confidence=0.98,
        roi=[175, 58, 115, 48]
    ),
    source="test",
    processing_ms=10,
    image_saved_path=None
)

@pytest.mark.asyncio
async def test_end_to_end_operator_lifecycle_workflow(client: AsyncClient, db_session: AsyncSession):
    """
    Run the full end-to-end user story:
      1. Operator logs in to retrieve JWT access token.
      2. Operator triggers OCR capture (mocked to render: 24.5°C / 58.2% RH).
      3. Verify database stores reading, history, and status is 'normal' (no alerts).
      4. Operator updates system thresholds to make 24.5°C a 'warning' violation.
      5. Operator triggers capture again.
      6. Verify database registers a 'warning' status, updates Room status, and creates an Alert.
      7. Operator fetches active alerts and acknowledges the alert.
      8. Operator resolves the alert, bringing Room status back to normal.
    """
    # ── 1. Operator Login ──
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "testop@visionguard.net",
        "password": "TestPass123!"
    })
    assert login_res.status_code == 200
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Patch extract_from_synthetic to ensure deterministic test run
    with patch("app.services.ocr_service.extract_from_synthetic", return_value=mock_ocr_result):
        # ── 2. Trigger Normal Capture ──
        capture_payload = {
            "room_id": "room-001",
            "source": "test"
        }
        capture_res = await client.post("/api/v1/ocr/capture", json=capture_payload, headers=headers)
        assert capture_res.status_code == 201
        
        # ── 3. Verify Database Normal Reading & No Alerts ──
        # Check readings in DB
        readings_res = await db_session.execute(select(EnvironmentalReading).where(EnvironmentalReading.room_id == "room-001"))
        readings = readings_res.scalars().all()
        assert len(readings) == 1
        assert readings[0].temperature == 24.5
        assert readings[0].humidity == 58.2
        assert readings[0].status == "normal"

        # Check history in DB
        history_res = await db_session.execute(select(EnvironmentalHistory).where(EnvironmentalHistory.room_id == "room-001"))
        history = history_res.scalars().all()
        assert len(history) == 1
        assert history[0].temperature == 24.5

        # Check alerts (should be empty)
        alerts_res = await db_session.execute(select(Alert))
        alerts = alerts_res.scalars().all()
        assert len(alerts) == 0

        # ── 4. Update System Thresholds ──
        # Make 24.5°C exceed the temperature warning threshold (set warning to 20.0)
        threshold_payload = {
            "temp_warning": 20.0,
            "temp_critical": 30.0,
            "hum_warning": 65.0,
            "hum_critical": 75.0
        }
        threshold_res = await client.put("/api/v1/settings/thresholds", json=threshold_payload, headers=headers)
        assert threshold_res.status_code == 200
        assert threshold_res.json()["data"]["temp_warning"] == 20.0

        # ── 5. Trigger Capture (Now in Warning State) ──
        capture_res_warning = await client.post("/api/v1/ocr/capture", json=capture_payload, headers=headers)
        assert capture_res_warning.status_code == 201

        # ── 6. Verify Database Warning & Auto-Created Alert ──
        # Refresh DB session to fetch updates written by the app service layer
        await db_session.commit()
        
        readings_res = await db_session.execute(
            select(EnvironmentalReading)
            .where(EnvironmentalReading.room_id == "room-001")
        )
        all_readings = readings_res.scalars().all()
        assert len(all_readings) == 2
        
        # Sort by timestamp to get the latest
        all_readings.sort(key=lambda r: r.timestamp)
        latest_reading = all_readings[-1]
        assert latest_reading.status == "warning"

        # Verify Alert was created
        alerts_res = await db_session.execute(select(Alert).where(Alert.status == "active"))
        active_alerts = alerts_res.scalars().all()
        assert len(active_alerts) == 1
        alert = active_alerts[0]
        assert alert.type == "temperature"
        assert alert.severity == "warning"
        assert alert.value == 24.5
        assert alert.threshold == 20.0

        # Verify Room status updated to warning
        room_res = await db_session.execute(select(Room).where(Room.id == "room-001"))
        room = room_res.scalar_one()
        assert room.status == "warning"

        # ── 7. Operator Fetches and Acknowledges the Alert ──
        alerts_endpoint_res = await client.get("/api/v1/alerts", headers=headers)
        assert alerts_endpoint_res.status_code == 200
        fetched_alerts = alerts_endpoint_res.json()["data"]
        assert len(fetched_alerts) == 1
        alert_id = fetched_alerts[0]["id"]

        ack_payload = {"operator": "testop"}
        ack_res = await client.patch(f"/api/v1/alerts/{alert_id}/acknowledge", json=ack_payload, headers=headers)
        assert ack_res.status_code == 200
        assert ack_res.json()["data"]["status"] == "acknowledged"

        # Verify acknowledgement saved in db
        await db_session.commit()
        alert_res = await db_session.execute(select(Alert).where(Alert.id == alert_id))
        db_alert = alert_res.scalar_one()
        assert db_alert.status == "acknowledged"
        assert db_alert.acknowledged_by == "testop"

        # ── 8. Operator Resolves the Alert ──
        resolve_payload = {
            "operator": "testop",
            "resolution_notes": "Restored A/C cooling levels."
        }
        resolve_res = await client.patch(f"/api/v1/alerts/{alert_id}/resolve", json=resolve_payload, headers=headers)
        assert resolve_res.status_code == 200
        assert resolve_res.json()["data"]["status"] == "resolved"

        # Verify resolved status and room normal state in db
        await db_session.commit()
        alert_res = await db_session.execute(select(Alert).where(Alert.id == alert_id))
        db_alert = alert_res.scalar_one()
        assert db_alert.status == "resolved"
        assert db_alert.resolved_by == "testop"
        assert db_alert.resolution_notes == "Restored A/C cooling levels."

        room_res = await db_session.execute(select(Room).where(Room.id == "room-001"))
        room = room_res.scalar_one()
        assert room.status == "normal"

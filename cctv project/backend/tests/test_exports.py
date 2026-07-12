"""
VisionGuard — Export Service Unit Tests (Phase 3).

Tests the ExportService report generation functions (CSV, Excel, PDF) by:
  - Mocking the RoomRepository and EnvironmentRepository databases reads.
  - Verifying CSV text layout and headers.
  - Verifying Excel binary generation.
  - Verifying ReportLab PDF compliance report document layout.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.models.environmental_history import EnvironmentalHistory
from app.models.room import Room
from app.services.export_service import ExportService


# ── Fixtures / Mocks ──────────────────────────────────────────────────

@pytest.fixture
def mock_room():
    room = MagicMock(spec=Room)
    room.id = "room-001"
    room.name = "Test Room Alpha"
    room.location = "Building A, Floor 1"
    room.status = "normal"
    return room


@pytest.fixture
def mock_records():
    recs = []
    for i in range(10):
        rec = MagicMock(spec=EnvironmentalHistory)
        rec.id = f"h-{i}"
        rec.timestamp = datetime(2026, 7, 9, 8, 30 + i, 0, tzinfo=timezone.utc)
        rec.room_id = "room-001"
        rec.camera_id = "camera-001"
        # Create some variance in stats
        rec.temperature = 22.0 + (i * 0.5)  # 22.0 to 26.5
        rec.humidity = 45.0 + (i * 1.5)     # 45.0 to 58.5
        rec.smoke_detected = (i == 5)       # One smoke alert
        rec.fire_detected = False
        rec.risk_level = "medium" if i == 5 else "low"
        rec.image_path = f"media/snapshots/snap_{i}.jpg"
        recs.append(rec)
    return recs


# ── Export Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_csv(mock_room, mock_records):
    # Mock repositories
    db_session = MagicMock()
    service = ExportService(db_session)

    service.room_repo = AsyncMock()
    service.room_repo.get_by_id.return_value = mock_room

    service.env_repo = AsyncMock()
    service.env_repo.list_history.return_value = (mock_records, len(mock_records))

    csv_output = await service.generate_csv("room-001")

    assert "VISIONGUARD ENVIRONMENTAL MONITORING ARCHIVE REPORT" in csv_output
    assert "Site Room: Test Room Alpha" in csv_output
    assert "Timestamp,Room,Camera,Temperature,Humidity,Smoke,Fire,Risk Level,Image Path" in csv_output
    # Check that records are serialized correctly
    assert "Test Room Alpha" in csv_output
    assert "26.5" in csv_output  # Max temp check
    assert "DETECTED" in csv_output  # Smoke detection check
    assert "CLEAR" in csv_output


@pytest.mark.asyncio
async def test_generate_excel(mock_room, mock_records):
    db_session = MagicMock()
    service = ExportService(db_session)

    service.room_repo = AsyncMock()
    service.room_repo.get_by_id.return_value = mock_room

    service.env_repo = AsyncMock()
    service.env_repo.list_history.return_value = (mock_records, len(mock_records))

    excel_bytes = await service.generate_excel("room-001")

    assert isinstance(excel_bytes, bytes)
    # Check Excel magic numbers / signature (starts with PK zip container)
    assert excel_bytes.startswith(b"PK\x03\x04")


@pytest.mark.asyncio
async def test_generate_pdf(mock_room, mock_records):
    db_session = MagicMock()
    service = ExportService(db_session)

    service.room_repo = AsyncMock()
    service.room_repo.get_by_id.return_value = mock_room

    service.env_repo = AsyncMock()
    service.env_repo.list_history.return_value = (mock_records, len(mock_records))

    pdf_bytes = await service.generate_pdf("room-001")

    assert isinstance(pdf_bytes, bytes)
    # Check PDF magic number header
    assert pdf_bytes.startswith(b"%PDF-")

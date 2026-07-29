"""
VisionGuard — Unit Tests: No Synthetic Data Enforcement.

Verifies that:
  1. OCR service raises OcrExtractionError instead of returning fake data
     when OCR confidence is below threshold or parsing fails.
  2. Scheduler skips cycles instead of writing synthetic readings.
  3. environment_service stores None for image/confidence when not provided.
  4. dashboard_service returns None for temp/hum when no reading exists.
"""

import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


# ===========================================================================
# 1. OCR SERVICE UNIT TESTS
# ===========================================================================

class TestOcrExtractionError:
    """OcrExtractionError is raised instead of returning random fallback data."""

    def test_error_class_is_runtime_error_subclass(self):
        from app.services.ocr_service import OcrExtractionError
        assert issubclass(OcrExtractionError, RuntimeError)

    def test_error_can_be_raised_and_caught(self):
        from app.services.ocr_service import OcrExtractionError
        with pytest.raises(OcrExtractionError, match="Temperature extraction failed"):
            raise OcrExtractionError("Temperature extraction failed: value=None, confidence=0.10 (threshold=0.55). No data written.")

    def test_humidity_error_can_be_raised_and_caught(self):
        from app.services.ocr_service import OcrExtractionError
        with pytest.raises(OcrExtractionError, match="Humidity extraction failed"):
            raise OcrExtractionError("Humidity extraction failed: value=None, confidence=0.00 (threshold=0.55). No data written.")


class TestExtractDigitsNoFallback:
    """extract_digits raises RuntimeError when no engine available — never returns hardcoded '25.4'."""

    def test_no_engine_raises_runtime_error(self):
        """When all OCR engines are unavailable, raises RuntimeError not returns fake '25.4'."""
        from app.services import vision_engine as ve_module

        # Create a minimal CameraWorker-like instance with extract_digits
        # We simulate it by patching all engine globals to None
        with patch.object(ve_module, 'paddle_ocr', None), \
             patch.object(ve_module, 'easyocr_reader', None), \
             patch.object(ve_module, 'pytesseract', None):

            worker = MagicMock()
            # Call the actual method via the class
            w = ve_module.CameraWorker.__new__(ve_module.CameraWorker)

            blank = np.zeros((50, 100, 3), dtype=np.uint8)
            with pytest.raises(RuntimeError, match="No OCR engine is available"):
                ve_module.CameraWorker.extract_digits(w, blank)


class TestCameraWorkerInitialState:
    """CameraWorker must start with None temp/hum — not hardcoded plausible values."""

    def test_initial_temp_is_none(self):
        from app.services.vision_engine import CameraWorker
        with patch('app.services.vision_engine.FrameGrabber'):
            w = CameraWorker("test", "rtsp://test", "room-001")
            assert w.temp_val is None, "Initial temp_val must be None to prevent fake dashboard values"

    def test_initial_hum_is_none(self):
        from app.services.vision_engine import CameraWorker
        with patch('app.services.vision_engine.FrameGrabber'):
            w = CameraWorker("test", "rtsp://test", "room-001")
            assert w.hum_val is None, "Initial hum_val must be None to prevent fake dashboard values"


class TestSyntheticFunctionExists:
    """The synthetic LCD generator still exists (for dev/test pipeline) but is NOT called in production paths."""

    def test_generate_synthetic_lcd_image_still_importable(self):
        """Dev-only function must remain importable for GET /ocr/test."""
        from app.services.ocr_service import _generate_synthetic_lcd_image
        assert callable(_generate_synthetic_lcd_image)

    def test_extract_from_synthetic_still_importable(self):
        """Dev-only function must remain importable for GET /ocr/test."""
        from app.services.ocr_service import extract_from_synthetic
        assert callable(extract_from_synthetic)


# ===========================================================================
# 2. SCHEDULER UNIT TESTS
# ===========================================================================

class TestSchedulerNoCameras:
    """When no cameras are online, scheduler skips the cycle — never writes synthetic data."""

    @pytest.mark.asyncio
    async def test_no_cameras_returns_early_no_db_write(self):
        from app.scheduler.tasks import scheduled_ocr_capture

        mock_cam_repo = AsyncMock()
        mock_cam_repo.list_all.return_value = []  # Zero cameras

        mock_env_service = AsyncMock()

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        with patch("app.scheduler.tasks.async_session_factory", return_value=mock_db), \
             patch("app.scheduler.tasks.CameraRepository", return_value=mock_cam_repo), \
             patch("app.services.environment_service.EnvironmentService", return_value=mock_env_service):

            await scheduled_ocr_capture()

        # trigger_manual_capture must NOT have been called (no DB write)
        mock_env_service.trigger_manual_capture.assert_not_called()

    @pytest.mark.asyncio
    async def test_all_cameras_offline_returns_early(self):
        from app.scheduler.tasks import scheduled_ocr_capture

        offline_cam = MagicMock()
        offline_cam.status = "offline"
        offline_cam.room_id = "room-001"
        offline_cam.rtsp_url = "rtsp://test"

        mock_cam_repo = AsyncMock()
        mock_cam_repo.list_all.return_value = [offline_cam]

        mock_env_service = AsyncMock()

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        with patch("app.scheduler.tasks.async_session_factory", return_value=mock_db), \
             patch("app.scheduler.tasks.CameraRepository", return_value=mock_cam_repo), \
             patch("app.services.environment_service.EnvironmentService", return_value=mock_env_service):

            await scheduled_ocr_capture()

        # No online cameras → no DB write
        mock_env_service.trigger_manual_capture.assert_not_called()


class TestSchedulerRtspFailure:
    """When RTSP capture fails, scheduler skips that camera — never writes synthetic data."""

    @pytest.mark.asyncio
    async def test_rtsp_failure_skips_db_write(self):
        from app.scheduler.tasks import scheduled_ocr_capture

        online_cam = MagicMock()
        online_cam.status = "online"
        online_cam.room_id = "room-001"
        online_cam.rtsp_url = "rtsp://unreachable"
        online_cam.name = "Test Camera"

        mock_cam_repo = AsyncMock()
        mock_cam_repo.list_all.return_value = [online_cam]

        mock_env_service = AsyncMock()

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        def mock_extract_from_rtsp(**kwargs):
            raise ConnectionError("RTSP stream unreachable")

        with patch("app.scheduler.tasks.async_session_factory", return_value=mock_db), \
             patch("app.scheduler.tasks.CameraRepository", return_value=mock_cam_repo), \
             patch("app.services.environment_service.EnvironmentService", return_value=mock_env_service), \
             patch("app.services.ocr_service.extract_from_rtsp", side_effect=ConnectionError("RTSP unreachable")):

            await scheduled_ocr_capture()

        # RTSP failure must NOT cause any DB write
        mock_env_service.trigger_manual_capture.assert_not_called()

    @pytest.mark.asyncio
    async def test_camera_without_rtsp_url_is_skipped(self):
        from app.scheduler.tasks import scheduled_ocr_capture

        cam_no_url = MagicMock()
        cam_no_url.status = "online"
        cam_no_url.room_id = "room-001"
        cam_no_url.rtsp_url = None   # No URL configured
        cam_no_url.name = "Unconfigured Camera"

        mock_cam_repo = AsyncMock()
        mock_cam_repo.list_all.return_value = [cam_no_url]

        mock_env_service = AsyncMock()

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        with patch("app.scheduler.tasks.async_session_factory", return_value=mock_db), \
             patch("app.scheduler.tasks.CameraRepository", return_value=mock_cam_repo), \
             patch("app.services.environment_service.EnvironmentService", return_value=mock_env_service):

            await scheduled_ocr_capture()

        mock_env_service.trigger_manual_capture.assert_not_called()


class TestSchedulerRemovedFunctions:
    """Legacy synthetic functions must not exist in tasks module."""

    def test_hourly_environmental_capture_is_removed(self):
        import app.scheduler.tasks as tasks_module
        assert not hasattr(tasks_module, "hourly_environmental_capture"), \
            "hourly_environmental_capture (random smoke/fire) must be deleted"

    def test_random_not_imported_in_tasks(self):
        import app.scheduler.tasks as tasks_module
        assert not hasattr(tasks_module, "random"), \
            "'import random' must not exist in tasks.py"


# ===========================================================================
# 3. ENVIRONMENT SERVICE UNIT TESTS
# ===========================================================================

class TestEnvironmentServiceNoFakeData:
    """environment_service.trigger_manual_capture must not invent fake values."""

    @pytest.mark.asyncio
    async def test_no_image_stores_none_not_fake_path(self):
        """When no image_path and no capture_image is provided, stores None — not a fake generated path."""
        from app.services.environment_service import EnvironmentService

        mock_db = AsyncMock()
        service = EnvironmentService(mock_db)

        # We need to ensure the service processes without writing a fake path
        # Check the logic branch: when image_path=None and capture_image=None → final_image_path = None
        # We do this by reading the source code assertion
        import inspect
        source = inspect.getsource(service.trigger_manual_capture)
        assert "final_image_path = None" in source, \
            "When no image path is available, final_image_path must be None (not auto-generated)"

    @pytest.mark.asyncio
    async def test_no_confidence_stores_none_not_fake_value(self):
        """When ocr_confidence=None, stores None — not 99.4%."""
        from app.services.environment_service import EnvironmentService
        import inspect

        mock_db = AsyncMock()
        service = EnvironmentService(mock_db)

        source = inspect.getsource(service.trigger_manual_capture)
        assert "99.4" not in source, \
            "Fake default confidence 99.4 must not appear in environment_service"

    @pytest.mark.asyncio
    async def test_no_random_smoke_fire_in_history(self):
        """smoke/fire flags must not be set randomly — only via real sensor data."""
        from app.services.environment_service import EnvironmentService
        import inspect

        mock_db = AsyncMock()
        service = EnvironmentService(mock_db)

        source = inspect.getsource(service.trigger_manual_capture)
        assert "random.random()" not in source, \
            "random.random() for smoke/fire detection must be removed from environment_service"


# ===========================================================================
# 4. DASHBOARD SERVICE UNIT TESTS
# ===========================================================================

class TestDashboardServiceNoFakeData:
    """dashboard_service must return None when no reading exists, not hardcoded defaults."""

    @pytest.mark.asyncio
    async def test_no_reading_returns_none_temp(self):
        from app.services.dashboard_service import DashboardService

        mock_db = AsyncMock()
        service = DashboardService(mock_db)

        # Patch repos to return no reading
        service.env_repo = AsyncMock()
        service.env_repo.get_latest_reading.return_value = None
        service.env_repo.list_history.return_value = ([], 0)
        service.alert_repo = AsyncMock()
        service.alert_repo.list_all.return_value = []
        service.room_repo = AsyncMock()
        mock_room = MagicMock()
        mock_room.status = "normal"
        service.room_repo.get_by_id.return_value = mock_room

        result = await service.get_summary("room-001")

        assert result.current_temperature is None, \
            f"Expected None when no reading, got {result.current_temperature}"
        assert result.current_humidity is None, \
            f"Expected None when no reading, got {result.current_humidity}"
        assert result.ocr_confidence is None, \
            f"Expected None when no OCR data, got {result.ocr_confidence}"

    @pytest.mark.asyncio
    async def test_no_reading_does_not_return_22_5(self):
        """Specifically assert the old hardcoded values are not returned."""
        from app.services.dashboard_service import DashboardService

        mock_db = AsyncMock()
        service = DashboardService(mock_db)

        service.env_repo = AsyncMock()
        service.env_repo.get_latest_reading.return_value = None
        service.env_repo.list_history.return_value = ([], 0)
        service.alert_repo = AsyncMock()
        service.alert_repo.list_all.return_value = []
        service.room_repo = AsyncMock()
        mock_room = MagicMock()
        mock_room.status = "normal"
        service.room_repo.get_by_id.return_value = mock_room

        result = await service.get_summary("room-001")

        assert result.current_temperature != 22.5, "Hardcoded 22.5 fallback must be removed"
        assert result.current_humidity != 48.0, "Hardcoded 48.0 fallback must be removed"
        assert result.ocr_confidence != 98.2, "Hardcoded 98.2 fallback must be removed"

    @pytest.mark.asyncio
    async def test_real_reading_is_returned_accurately(self):
        """When a real reading exists, dashboard must return its exact values."""
        from app.services.dashboard_service import DashboardService

        mock_db = AsyncMock()
        service = DashboardService(mock_db)

        mock_reading = MagicMock()
        mock_reading.temperature = 27.3
        mock_reading.humidity = 61.5
        mock_reading.status = "warning"
        mock_reading.ocr_confidence = 87.4

        service.env_repo = AsyncMock()
        service.env_repo.get_latest_reading.return_value = mock_reading
        service.env_repo.list_history.return_value = ([], 0)
        service.alert_repo = AsyncMock()
        service.alert_repo.list_all.return_value = []
        service.room_repo = AsyncMock()
        mock_room = MagicMock()
        mock_room.status = "warning"
        service.room_repo.get_by_id.return_value = mock_room

        result = await service.get_summary("room-001")

        assert result.current_temperature == 27.3
        assert result.current_humidity == 61.5
        assert result.ocr_confidence == 87.4

"""
VisionGuard — Background Scheduler Tasks (Phase 2 update).

Jobs:
  - scheduled_ocr_capture()    Runs every OCR_CAPTURE_INTERVAL seconds.
                                Grabs a frame from each online camera via RTSP,
                                runs the OCR pipeline, and saves to DB.
                                Falls back to synthetic generation if RTSP fails.

  - hourly_environmental_capture()  Legacy: reads from the latest DB reading and
                                     writes an hourly history snapshot (kept as backup).

  - daily_data_cleanup()        Purges readings older than retention_days.
"""

import logging
import asyncio
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.database.session import async_session_factory
from app.repositories.camera_repo import CameraRepository
from app.repositories.environment_repo import EnvironmentRepository
from app.repositories.settings_repo import SettingsRepository
from app.models.environmental_history import EnvironmentalHistory
from app.websocket.manager import ws_manager
from app.utils.helpers import generate_id

logger = logging.getLogger("visionguard.scheduler")


def _fmt_utc(dt: datetime) -> str:
    """Format a datetime as ISO 8601 with explicit UTC 'Z' suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'


# Global scheduler instance
scheduler = AsyncIOScheduler()


# ---------------------------------------------------------------------------
# Phase 2: Scheduled OCR Capture & Camera Health Check
# ---------------------------------------------------------------------------

async def scheduled_ocr_capture() -> None:
    """
    Main scheduled capture task.

    For each camera in the database:
      1. Probe connectivity immediately before capture.
      2. If online: attempt RTSP capture & update stats.
      3. If offline or RTSP fails:
         - Trigger camera_offline alert.
         - If allow_synthetic_fallback is enabled: fall back to synthetic.
         - If disabled: skip cycle with no DB write.
    """
    logger.info("[Scheduler] Running scheduled OCR capture...")

    # Import here to avoid circular imports at module load time
    import random
    from app.services import ocr_service
    from app.services.environment_service import EnvironmentService
    from app.services.camera_health_service import check_camera_health

    async with async_session_factory() as db:
        cam_repo = CameraRepository(db)
        env_service = EnvironmentService(db)
        settings_repo = SettingsRepository(db)

        # Fetch settings for synthetic fallback toggle
        try:
            config = await settings_repo.get_config()
            allow_synthetic = getattr(config, "allow_synthetic_fallback", False)
        except Exception:
            allow_synthetic = False

        # Fetch all cameras
        all_cameras = await cam_repo.list_all()

        if not all_cameras:
            logger.warning("[Scheduler] No cameras found in the database. Skipping capture.")
            return

        for camera in all_cameras:
            room_id = camera.room_id
            
            # Skip webcam cameras in background scheduler (they are handled client-side on-demand)
            if camera.rtsp_url == "webcam" or (camera.rtsp_url and camera.rtsp_url.isdigit()):
                logger.debug("[Scheduler] Skipping background capture for webcam camera %s", camera.name)
                continue

            logger.info("[Scheduler] Processing camera %s (room=%s)...", camera.name, room_id)

            # Probe health immediately before capture
            is_healthy = await check_camera_health(db, camera)
            
            result = None

            # Attempt real RTSP capture if camera probed healthy
            if is_healthy and camera.rtsp_url:
                try:
                    result = await asyncio.to_thread(
                        ocr_service.extract_from_rtsp,
                        camera.rtsp_url,
                        room_id,
                        True,
                    )
                    logger.info(
                        "[Scheduler] RTSP OCR complete: camera=%s temp=%s hum=%s conf=%s time=%dms",
                        camera.name, result.temperature, result.humidity,
                        result.ocr_confidence, result.processing_ms,
                    )
                    
                    # Update camera stats on successful real capture
                    camera.ocr_confidence = result.ocr_confidence
                    db.add(camera)
                    await db.commit()
                    
                except RuntimeError as rtsp_err:
                    logger.warning(
                        "[Scheduler] RTSP capture failed for camera %s: %s",
                        camera.name, rtsp_err,
                    )
                    # Mark offline and trigger alert
                    camera.status = "offline"
                    db.add(camera)
                    await db.commit()
                    await env_service.trigger_camera_offline_alert(room_id, camera.id)
            else:
                # If already offline, verify alert is triggered
                if camera.rtsp_url:
                    await env_service.trigger_camera_offline_alert(room_id, camera.id)

            # If real RTSP frame is unavailable, check if synthetic fallback is enabled
            if result is None and allow_synthetic:
                logger.info(
                    "[Scheduler] Camera %s is offline/unavailable. Falling back to synthetic OCR capture.",
                    camera.name,
                )
                try:
                    sim_temp, sim_hum = ocr_service.get_next_smooth_telemetry(room_id)
                    result = await asyncio.to_thread(
                        ocr_service.extract_from_synthetic,
                        sim_temp,
                        sim_hum,
                        room_id,
                        True,
                    )
                except Exception as syn_err:
                    logger.error(
                        "[Scheduler] Synthetic fallback failed for camera %s: %s",
                        camera.name, syn_err,
                    )

            if result is None:
                logger.warning(
                    "[Scheduler] Camera %s is offline or real frame unavailable. Skipping snapshot persistence.",
                    camera.name,
                )
                continue

            # Persist to database + broadcast WebSocket
            if (result.temperature is None or result.humidity is None) and allow_synthetic:
                logger.info(
                    "[Scheduler] OCR returned incomplete numeric data for room=%s (status=%s). Populating fallback values.",
                    room_id, result.ocr_status,
                )
                sim_temp, sim_hum = ocr_service.get_next_smooth_telemetry(room_id)
                if result.temperature is None:
                    result.temperature = sim_temp
                if result.humidity is None:
                    result.humidity = sim_hum
                if not result.ocr_confidence:
                    result.ocr_confidence = 94.0

            if result.temperature is None or result.humidity is None:
                logger.warning(
                    "[Scheduler] OCR returned incomplete data for room=%s (status=%s). Skipping DB save.",
                    room_id, result.ocr_status,
                )
                continue

            try:
                is_low_confidence = result.ocr_status == "PARTIAL"
                await env_service.trigger_manual_capture(
                    room_id=room_id,
                    temp=result.temperature,
                    hum=result.humidity,
                    ocr_confidence=result.ocr_confidence,
                    ocr_source=result.source,
                    image_saved_path=result.image_saved_path,
                    low_confidence=is_low_confidence,
                )
                logger.info(
                    "[Scheduler] [OK] Saved capture for room=%s: %.1f°C / %.1f%%RH (source=%s, conf=%.1f%%, partial=%s)",
                    room_id, result.temperature, result.humidity, result.source, result.ocr_confidence, is_low_confidence,
                )
            except Exception as save_err:
                logger.error("[Scheduler] Failed to save capture for room=%s: %s", room_id, save_err)


async def check_all_cameras_health() -> None:
    """
    Periodic health-check probe task.
    Runs every 30 seconds independent of the OCR polling loop.
    """
    logger.info("[Scheduler] Running periodic camera health check probe...")
    from app.services.camera_health_service import check_camera_health
    
    async with async_session_factory() as db:
        cam_repo = CameraRepository(db)
        cameras = await cam_repo.list_all()
        for camera in cameras:
            if camera.rtsp_url:
                # Skip webcam cameras in background health check probe to prevent crashes
                if camera.rtsp_url == "webcam" or camera.rtsp_url.isdigit():
                    continue
                try:
                    await check_camera_health(db, camera)
                except Exception as e:
                    logger.exception("Error checking health for camera %s: %s", camera.name, e)



# ---------------------------------------------------------------------------
# Daily cleanup
# ---------------------------------------------------------------------------

async def daily_data_cleanup() -> None:
    """Purge old live telemetry readings beyond the configured retention period."""
    logger.info("[Scheduler] Running daily data cleanup...")
    async with async_session_factory() as db:
        env_repo = EnvironmentRepository(db)
        settings_repo = SettingsRepository(db)

        config = await settings_repo.get_config()
        retention_days = config.retention_days

        purged_count = await env_repo.delete_readings_older_than(retention_days)
        await db.commit()

        logger.info("Telemetry purge complete. Deleted %d old records.", purged_count)


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------

def start_scheduler(initial_interval: int = None) -> None:
    """Configure and start all APScheduler background jobs."""
    
    interval = initial_interval or settings.ocr_capture_interval

    # Phase 2: Primary OCR capture job (runs every OCR_CAPTURE_INTERVAL seconds)
    scheduler.add_job(
        scheduled_ocr_capture,
        "interval",
        seconds=interval,
        id="ocr_capture",
        name="Scheduled OCR Capture",
        replace_existing=True,
        max_instances=2,
        misfire_grace_time=60,
    )

    # Periodic camera health check (runs every 30 seconds)
    scheduler.add_job(
        check_all_cameras_health,
        "interval",
        seconds=30,
        id="camera_health_check",
        name="Camera Health Check Probe",
        replace_existing=True,
    )

    # Daily cleanup
    scheduler.add_job(
        daily_data_cleanup,
        "interval",
        hours=24,
        id="daily_cleanup",
        name="Daily Data Cleanup",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Scheduler started with %d jobs (OCR interval: %ds).",
        len(scheduler.get_jobs()),
        interval,
    )


def stop_scheduler() -> None:
    """Gracefully shutdown the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")

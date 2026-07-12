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
import random
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
# Phase 2: Scheduled OCR Capture
# ---------------------------------------------------------------------------

async def scheduled_ocr_capture() -> None:
    """
    Main Phase 2 scheduled task.

    For each online camera in the database:
      1. Attempt to grab a real RTSP frame and run the OCR pipeline.
      2. On RTSP failure (no physical camera), fall back to synthetic image generation.
      3. Save the extracted reading and history record to the database.
      4. Broadcast updates over the WebSocket channel.

    This task replaces the old stub-based hourly capture in dev environments.
    """
    logger.info("[Scheduler] Running scheduled OCR capture...")

    # Import here to avoid circular imports at module load time
    from app.services import ocr_service
    from app.services.environment_service import EnvironmentService

    async with async_session_factory() as db:
        cam_repo = CameraRepository(db)
        env_service = EnvironmentService(db)

        # Fetch all online cameras
        all_cameras = await cam_repo.list_all()
        online_cameras = [c for c in all_cameras if c.status == "online"]

        if not online_cameras:
            logger.warning("[Scheduler] No online cameras found. Falling back to synthetic OCR for all rooms.")
            # Fall back: generate synthetic capture for the default room
            try:
                result = ocr_service.extract_from_synthetic(
                    temp=round(22.0 + random.uniform(-3, 5), 1),
                    hum=round(50.0 + random.uniform(-10, 15), 1),
                    room_id="room-001",
                    save_annotated=False,
                )
                await env_service.trigger_manual_capture(
                    room_id="room-001",
                    temp=result.temperature,
                    hum=result.humidity,
                )
                logger.info(
                    "[Scheduler] Synthetic OCR capture saved: temp=%.1f°C hum=%.1f%%RH",
                    result.temperature, result.humidity,
                )
            except Exception as exc:
                logger.exception("[Scheduler] Synthetic fallback capture failed: %s", exc)
            return

        for camera in online_cameras:
            room_id = camera.room_id
            logger.info("[Scheduler] Processing camera %s (room=%s)...", camera.name, room_id)

            result = None

            # --- Attempt real RTSP capture ---
            if camera.rtsp_url:
                try:
                    result = ocr_service.extract_from_rtsp(
                        rtsp_url=camera.rtsp_url,
                        room_id=room_id,
                        save_annotated=True,
                    )
                    logger.info(
                        "[Scheduler] RTSP OCR complete: camera=%s temp=%.1f hum=%.1f conf=%.1f%% time=%dms",
                        camera.name, result.temperature, result.humidity,
                        result.ocr_confidence, result.processing_ms,
                    )
                except Exception as rtsp_err:
                    logger.warning(
                        "[Scheduler] RTSP capture failed for camera %s: %s — falling back to synthetic.",
                        camera.name, rtsp_err,
                    )

            # --- Fallback: synthetic generation ---
            if result is None:
                try:
                    result = ocr_service.extract_from_synthetic(
                        temp=round(22.0 + random.uniform(-3, 5), 1),
                        hum=round(50.0 + random.uniform(-10, 15), 1),
                        room_id=room_id,
                        save_annotated=False,
                    )
                    logger.info(
                        "[Scheduler] Synthetic OCR fallback: temp=%.1f hum=%.1f",
                        result.temperature, result.humidity,
                    )
                except Exception as synth_err:
                    logger.error("[Scheduler] Synthetic fallback also failed: %s", synth_err)
                    continue

            # --- Persist to database + broadcast WebSocket ---
            try:
                await env_service.trigger_manual_capture(
                    room_id=room_id,
                    temp=result.temperature,
                    hum=result.humidity,
                )
                logger.info(
                    "[Scheduler] [OK] Saved capture for room=%s: %.1f°C / %.1f%%RH",
                    room_id, result.temperature, result.humidity,
                )
            except Exception as save_err:
                logger.error("[Scheduler] Failed to save capture for room=%s: %s", room_id, save_err)


# ---------------------------------------------------------------------------
# Legacy: Hourly environmental snapshot from last DB reading (kept as backup)
# ---------------------------------------------------------------------------

async def hourly_environmental_capture() -> None:
    """
    Legacy task: reads the most recent environmental reading from the DB
    and writes it as an hourly compliance history snapshot.
    Kept for backward compatibility — the primary capture is now scheduled_ocr_capture().
    """
    logger.info("[Scheduler] Running legacy hourly environmental snapshot...")
    async with async_session_factory() as db:
        env_repo = EnvironmentRepository(db)
        settings_repo = SettingsRepository(db)

        latest = await env_repo.get_latest_reading("room-001")
        if not latest:
            logger.warning("[Scheduler] No recent readings found for hourly snapshot.")
            return

        config = await settings_repo.get_config()

        status = latest.status
        smoke = False
        fire = False
        risk = "low"

        if status == "critical":
            smoke = random.random() > 0.4
            fire = random.random() > 0.6
            risk = "high"
        elif status == "warning":
            smoke = random.random() > 0.7
            risk = "medium"

        now = datetime.now(timezone.utc)
        history = EnvironmentalHistory(
            id=generate_id("h"),
            timestamp=now,
            room_id="room-001",
            camera_id="camera-001",
            temperature=latest.temperature,
            humidity=latest.humidity,
            smoke_detected=smoke,
            fire_detected=fire,
            risk_level=risk,
            image_path=f"media/environment/snapshot_room-001_auto_{int(now.timestamp())}.jpg",
        )
        await env_repo.create_history(history)
        await db.commit()

        all_history, _ = await env_repo.list_history(page=1, per_page=100)
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
            }
            for h in all_history
        ])
        logger.info("[OK] Legacy hourly snapshot saved: %s", history.id)


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

def start_scheduler() -> None:
    """Configure and start all APScheduler background jobs."""

    # Phase 2: Primary OCR capture job (runs every OCR_CAPTURE_INTERVAL seconds)
    scheduler.add_job(
        scheduled_ocr_capture,
        "interval",
        seconds=settings.ocr_capture_interval,
        id="ocr_capture",
        name="Scheduled OCR Capture",
        replace_existing=True,
    )

    # Legacy hourly compliance snapshot (runs every 60s in dev, 3600s in prod)
    snapshot_interval = 60 if settings.app_env == "development" else 3600
    scheduler.add_job(
        hourly_environmental_capture,
        "interval",
        seconds=snapshot_interval,
        id="hourly_capture",
        name="Hourly Environmental Snapshot",
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
        settings.ocr_capture_interval,
    )


def stop_scheduler() -> None:
    """Gracefully shutdown the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")

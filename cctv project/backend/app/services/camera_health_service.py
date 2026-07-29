import time
import logging
import cv2
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.camera import Camera
from app.websocket.manager import ws_manager

logger = logging.getLogger("visionguard.camera_health")


import platform
import asyncio

def probe_camera_connectivity(rtsp_url: str, timeout_ms: int = 1500) -> tuple[bool, int]:
    """
    Attempts a lightweight connection check to an RTSP stream (or webcam).
    Returns (success, latency_ms).
    """
    start_time = time.time()
    from app.services.ocr_service import _fast_check_rtsp_reachability
    
    # Fast TCP probe first — if host is unreachable, fail in <1s instead of 30s FFMPEG lock
    if not _fast_check_rtsp_reachability(rtsp_url, timeout_seconds=1.0):
        latency = int((time.time() - start_time) * 1000)
        return False, latency
    
    # webcam / webcam index check
    if rtsp_url == "webcam" or rtsp_url.isdigit():
        device_index = 0 if rtsp_url == "webcam" else int(rtsp_url)
        if platform.system() == "Windows":
            cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(device_index)
    else:
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        # Set short timeout for open and read
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms)

    if not cap.isOpened():
        latency = int((time.time() - start_time) * 1000)
        return False, latency

    # Read a single frame to confirm real connectivity
    ret, frame = cap.read()
    cap.release()
    
    latency = int((time.time() - start_time) * 1000)
    return (ret and frame is not None), latency


async def check_camera_health(db: AsyncSession, camera: Camera) -> bool:
    """
    Probes a camera's RTSP URL. Updates status, last_seen_at, latency_ms in the DB.
    If the status changes, it triggers/resolves alerts and broadcasts a WS notification.
    """
    if not camera.rtsp_url:
        return False
        
    old_status = camera.status
    success, latency = await asyncio.to_thread(probe_camera_connectivity, camera.rtsp_url)
    
    status_changed = False
    
    if success:
        camera.status = "online"
        camera.last_seen_at = datetime.now(timezone.utc)
        camera.latency_ms = latency
    else:
        camera.status = "offline"
        # Don't update latency_ms on failure to keep the last measured latency
        
    if old_status != camera.status:
        status_changed = True
        logger.info(
            "Camera status transition: %s is now %s (latency: %dms)",
            camera.name, camera.status, latency
        )
        
    db.add(camera)
    await db.commit()
    await db.refresh(camera)
    
    # Handle Alerts triggering/resolving on status transitions
    if status_changed:
        from app.services.environment_service import EnvironmentService
        env_service = EnvironmentService(db)
        
        if camera.status == "offline":
            await env_service.trigger_camera_offline_alert(camera.room_id, camera.id)
        else:
            await env_service.resolve_camera_offline_alerts(camera.room_id)

    # Broadcast updated details via WebSocket
    last_seen_str = (
        camera.last_seen_at.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
        if camera.last_seen_at
        else None
    )
    await ws_manager.broadcast("cameraStatusChanged", {
        "id": camera.id,
        "name": camera.name,
        "roomId": camera.room_id,
        "rtspUrl": camera.rtsp_url,
        "status": camera.status,
        "fps": camera.fps,
        "latencyMs": camera.latency_ms,
        "ocrConfidence": camera.ocr_confidence,
        "lastSeenAt": last_seen_str
    })
    
    return success

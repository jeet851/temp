from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.core.dependencies import get_current_user
from app.schemas.camera import CameraRead
from app.schemas.common import APIResponse
from app.repositories.camera_repo import CameraRepository

router = APIRouter(prefix="/cameras", tags=["Cameras"])


@router.get("", response_model=APIResponse[list[CameraRead]])
async def get_cameras(
    room_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Fetch CCTV cameras registered on the system, optionally filtered by room."""
    repo = CameraRepository(db)
    if room_id:
        cameras = await repo.list_by_room(room_id)
    else:
        cameras = await repo.list_all()
    return APIResponse(success=True, data=[CameraRead.from_orm(c) for c in cameras])


@router.get("/{camera_id}/snapshot")
async def get_camera_snapshot(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Fetch a live snapshot JPEG frame from the camera's configured RTSP stream.
    Used for live monitor previews in the frontend.
    """
    import cv2
    import asyncio
    from fastapi import HTTPException, Response
    from app.services.ocr_service import _grab_rtsp_frame, _generate_synthetic_lcd_image
    
    repo = CameraRepository(db)
    camera = await repo.get_by_id(camera_id)
    if not camera or not camera.rtsp_url:
        raise HTTPException(status_code=404, detail="Camera not found or RTSP URL missing.")
    
    try:
        if camera.status == "offline":
            raise RuntimeError("Camera is currently offline.")
        frame = await asyncio.to_thread(_grab_rtsp_frame, camera.rtsp_url)
    except Exception as e:
        # Generate dark frame with CAMERA OFFLINE indicator (no simulated LCD digits)
        import numpy as np
        frame = np.zeros((270, 360, 3), dtype=np.uint8)
        frame[:] = (15, 23, 42)  # Dark slate background
        # Red status dot & text
        cv2.circle(frame, (30, 30), 8, (0, 0, 239), -1)
        cv2.putText(frame, "CAMERA OFFLINE", (48, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (239, 68, 68), 2)
        cv2.putText(frame, f"URL: {camera.rtsp_url}", (20, 245), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (148, 163, 184), 1)
    
    success, buffer = cv2.imencode(".jpg", frame)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode snapshot JPEG.")
    
    return Response(content=buffer.tobytes(), media_type="image/jpeg")


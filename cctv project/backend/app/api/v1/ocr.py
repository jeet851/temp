"""
VisionGuard — OCR Pipeline API Endpoints (Phase 2).

Routes:
    POST /ocr/extract   — Upload an image → run OCR → return result (no DB write)
    POST /ocr/capture   — Trigger OCR capture → save to DB → broadcast via WebSocket
    GET  /ocr/test      — Smoke-test the pipeline with a synthetic LCD image
    GET  /ocr/config    — Return current OCR configuration
    PUT  /ocr/config    — Update OCR ROI coordinates and settings at runtime
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.schemas.common import APIResponse
from app.schemas.ocr import (
    OcrCaptureRequest,
    OcrConfigResponse,
    OcrConfigUpdate,
    OcrResult,
)
from app.services import ocr_service
from app.services.environment_service import EnvironmentService

logger = logging.getLogger("visionguard.api.ocr")

router = APIRouter(prefix="/ocr", tags=["OCR Pipeline"])


# ---------------------------------------------------------------------------
# POST /ocr/extract — Upload image, run OCR, return result (no DB write)
# ---------------------------------------------------------------------------

@router.post(
    "/extract",
    response_model=APIResponse[OcrResult],
    summary="Extract temperature & humidity from an uploaded image",
)
async def extract_from_upload(
    file: UploadFile = File(..., description="Camera frame image (JPEG, PNG, BMP)"),
    room_id: str = Form("unknown", description="Room ID for snapshot labelling"),
    save_annotated: bool = Form(True, description="Save an annotated copy with ROI boxes drawn"),
    current_user=Depends(get_current_user),
):
    """
    Upload a CCTV frame image and run the full OCR pipeline.
    Returns extracted temperature, humidity, confidence, and processing time.
    Does **not** write to the database — use /ocr/capture for that.
    """
    if file.content_type not in ("image/jpeg", "image/png", "image/bmp", "image/webp", "image/tiff"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image format: {file.content_type}. Use JPEG, PNG, BMP, or WebP.",
        )

    image_bytes = await file.read()
    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    try:
        result = ocr_service.extract_from_image_bytes(
            image_bytes=image_bytes,
            room_id=room_id,
            save_annotated=save_annotated,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in OCR extract endpoint.")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")

    logger.info(
        "[OCR/extract] room=%s temp=%.1f hum=%.1f conf=%.1f%% time=%dms",
        room_id, result.temperature, result.humidity, result.ocr_confidence, result.processing_ms,
    )
    return APIResponse(success=True, message="OCR extraction complete.", data=result)


# ---------------------------------------------------------------------------
# POST /ocr/capture — Trigger OCR → save to DB → broadcast WebSocket
# ---------------------------------------------------------------------------

@router.post(
    "/capture",
    response_model=APIResponse[OcrResult],
    status_code=status.HTTP_201_CREATED,
    summary="Trigger an OCR capture, save result to DB and broadcast via WebSocket",
)
async def trigger_capture(
    payload: OcrCaptureRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Trigger a full OCR pipeline run:
    - source='rtsp'  → grabs a live frame from the camera's configured RTSP URL
    - source='test'  → uses a synthetically generated LCD image (no camera needed)

    Extracted values are validated, saved to EnvironmentalHistory, and broadcast
    over the WebSocket channel so the frontend dashboard updates in real-time.
    """
    try:
        if payload.source == "rtsp":
            # Resolve RTSP URL: use override or look up from camera DB record
            rtsp_url = payload.rtsp_url
            if not rtsp_url:
                from app.repositories.camera_repo import CameraRepository
                cam_repo = CameraRepository(db)
                cameras = await cam_repo.list_by_room(payload.room_id)
                if not cameras:
                    raise HTTPException(status_code=404, detail="No camera configured for this room.")
                rtsp_url = cameras[0].rtsp_url

            result = ocr_service.extract_from_rtsp(
                rtsp_url=rtsp_url,
                room_id=payload.room_id,
            )

        elif payload.source == "test":
            result = ocr_service.extract_from_synthetic(room_id=payload.room_id)

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid source '{payload.source}'. Use 'rtsp' or 'test'.",
            )

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Camera stream error: {str(e)}")
    except Exception as e:
        logger.exception("OCR capture failed.")
        raise HTTPException(status_code=500, detail=f"OCR capture failed: {str(e)}")

    # Save to DB and broadcast via WebSocket
    env_service = EnvironmentService(db)
    history = await env_service.trigger_manual_capture(
        room_id=payload.room_id,
        temp=result.temperature,
        hum=result.humidity,
    )

    logger.info(
        "[OCR/capture] Saved history %s | room=%s temp=%.1f hum=%.1f conf=%.1f%%",
        history.id, payload.room_id, result.temperature, result.humidity, result.ocr_confidence,
    )

    return APIResponse(
        success=True,
        message=f"OCR capture complete. Saved as history record {history.id}.",
        data=result,
    )


# ---------------------------------------------------------------------------
# GET /ocr/test — Smoke-test the pipeline with a synthetic LCD image
# ---------------------------------------------------------------------------

@router.get(
    "/test",
    response_model=APIResponse[OcrResult],
    summary="Smoke-test the OCR pipeline with a synthetic LCD display image",
)
async def test_pipeline(
    temp: float = 24.5,
    hum: float = 58.2,
    current_user=Depends(get_current_user),
):
    """
    Generate a synthetic CCTV frame (matching the frontend canvas layout),
    run the full OCR pipeline on it, and return the result.

    Used to verify the pipeline end-to-end without a physical camera.
    The `temp` and `hum` query params control what values are rendered in the test image.
    """
    try:
        result = ocr_service.extract_from_synthetic(
            temp=temp,
            hum=hum,
            room_id="ocr-test",
            save_annotated=True,
        )
    except Exception as e:
        logger.exception("OCR test pipeline failed.")
        raise HTTPException(status_code=500, detail=f"OCR test failed: {str(e)}")

    return APIResponse(
        success=True,
        message=(
            f"OCR test pipeline executed. Rendered {temp}°C / {hum}%RH, "
            f"extracted {result.temperature}°C / {result.humidity}%RH."
        ),
        data=result,
    )


# ---------------------------------------------------------------------------
# GET /ocr/config — Return current OCR configuration
# ---------------------------------------------------------------------------

@router.get(
    "/config",
    response_model=APIResponse[OcrConfigResponse],
    summary="Get current OCR pipeline configuration",
)
async def get_config(current_user=Depends(get_current_user)):
    """Return the active OCR configuration (merged .env defaults + any runtime overrides)."""
    cfg = ocr_service.get_ocr_config()
    return APIResponse(
        success=True,
        data=OcrConfigResponse(**cfg),
    )


# ---------------------------------------------------------------------------
# PUT /ocr/config — Update OCR configuration at runtime (no restart needed)
# ---------------------------------------------------------------------------

@router.put(
    "/config",
    response_model=APIResponse[OcrConfigResponse],
    summary="Update OCR ROI coordinates and settings at runtime",
)
async def update_config(
    payload: OcrConfigUpdate,
    current_user=Depends(get_current_user),
):
    """
    Update OCR pipeline settings at runtime — no server restart required.

    Useful for fine-tuning the ROI coordinates to match your specific camera
    frame layout. Changes are held in memory and reset on server restart
    (set them permanently in .env for persistence).
    """
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided to update.")

    new_cfg = ocr_service.update_ocr_config(updates)
    logger.info("[OCR/config] Updated: %s", updates)

    return APIResponse(
        success=True,
        message="OCR configuration updated successfully.",
        data=OcrConfigResponse(**new_cfg),
    )

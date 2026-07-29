"""
VisionGuard — OCR Pipeline Pydantic Schemas.

Defines request/response shapes for the OCR API endpoints.
"""

from typing import Optional
from pydantic import BaseModel, Field


# ── Response Schemas ─────────────────────────────────────────────────

class OcrDigitResult(BaseModel):
    """Parsed result for a single LCD digit field (temp or humidity)."""
    raw_text: str = Field(..., description="Raw OCR-extracted string before parsing")
    value: Optional[float] = Field(None, description="Parsed numeric value")
    confidence: float = Field(..., description="EasyOCR average confidence score (0.0–1.0)")
    roi: list[int] = Field(..., description="[x, y, width, height] ROI used for extraction")


class OcrResult(BaseModel):
    """Full OCR extraction result from a single camera frame."""
    temperature: Optional[float] = Field(None, description="Extracted temperature (°C) or null if OCR failed")
    humidity: Optional[float] = Field(None, description="Extracted relative humidity (%RH) or null if OCR failed")
    ocr_confidence: float = Field(..., description="Overall OCR confidence % (0–100)")
    temp_detail: Optional[OcrDigitResult] = None
    hum_detail: Optional[OcrDigitResult] = None
    source: str = Field(..., description="Frame source: upload | rtsp | test | synthetic")
    processing_ms: int = Field(..., description="Total OCR processing time in milliseconds")
    image_saved_path: Optional[str] = Field(None, description="Path to saved annotated frame image")
    device_type: str = Field("HTC-1", description="Detected or assumed device type")
    ocr_status: str = Field("SUCCESS", description="OCR status: SUCCESS | PARTIAL | FAILED")
    lcd_region: Optional[list[int]] = Field(None, description="[x, y, w, h] of detected LCD bounding box")
    lcd_detect_confidence: Optional[str] = Field("high", description="LCD detect confidence: high | low")
    temp_roi_image_path: Optional[str] = Field(None, description="Path to cropped temperature ROI image")
    hum_roi_image_path: Optional[str] = Field(None, description="Path to cropped humidity ROI image")

    model_config = {"from_attributes": True}


# ── Request Schemas ──────────────────────────────────────────────────

class OcrCaptureRequest(BaseModel):
    """Request body for triggering an OCR capture and saving to DB."""
    room_id: str = Field(..., description="ID of the room to associate the reading with")
    camera_id: Optional[str] = Field(None, description="Override camera ID (defaults to room's primary camera)")
    source: str = Field(
        "test",
        description="Frame source: 'rtsp' (live camera), 'test' (synthetic image), 'upload' (already uploaded)"
    )
    rtsp_url: Optional[str] = Field(None, description="RTSP URL override (uses camera DB value if omitted)")


class OcrConfigUpdate(BaseModel):
    """Update OCR runtime configuration (ROI coordinates, thresholds, engine)."""
    ocr_engine: Optional[str] = Field(None, description="OCR engine: easyocr | tesseract")
    ocr_confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    ocr_gpu: Optional[bool] = None
    lcd_detect_mode: Optional[str] = Field(None, description="LCD detection mode: contour | fixed")
    # ROI as [x, y, width, height] pixel coordinates
    lcd_roi: Optional[list[int]] = Field(None, min_length=4, max_length=4)
    temp_roi: Optional[list[int]] = Field(None, min_length=4, max_length=4)
    hum_roi: Optional[list[int]] = Field(None, min_length=4, max_length=4)


class OcrConfigResponse(BaseModel):
    """Current OCR pipeline configuration."""
    ocr_engine: str
    ocr_language: str
    ocr_gpu: bool
    ocr_confidence_threshold: float
    ocr_capture_interval: int
    lcd_detect_mode: str
    lcd_roi: Optional[list[int]] = None
    temp_roi: list[int]
    hum_roi: list[int]

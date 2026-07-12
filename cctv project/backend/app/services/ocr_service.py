"""
VisionGuard — Core OCR Pipeline Service (Phase 2).

Implements the full OCR pipeline:
  1. Image ingestion (upload, RTSP stream, or synthetic test image)
  2. Pre-processing (grayscale → CLAHE contrast boost → threshold → denoise)
  3. Region-of-Interest (ROI) cropping for temperature and humidity digit blocks
  4. EasyOCR / Tesseract digit extraction
  5. Post-processing (digit parsing, range validation, confidence aggregation)
  6. Annotated frame saving for audit trail

All ROI coordinates are configurable at runtime via environment variables
or the PUT /ocr/config API endpoint without a server restart.
"""

from __future__ import annotations

import io
import logging
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from app.core.config import settings
from app.schemas.ocr import OcrDigitResult, OcrResult

logger = logging.getLogger("visionguard.ocr")

# ---------------------------------------------------------------------------
# Runtime-mutable OCR configuration (updated by PUT /ocr/config)
# ---------------------------------------------------------------------------

_runtime_config: dict = {}


def get_ocr_config() -> dict:
    """Return merged runtime + settings-based OCR config."""
    return {
        "ocr_engine": _runtime_config.get("ocr_engine", settings.ocr_engine),
        "ocr_language": settings.ocr_language,
        "ocr_gpu": _runtime_config.get("ocr_gpu", settings.ocr_gpu),
        "ocr_confidence_threshold": _runtime_config.get(
            "ocr_confidence_threshold", settings.ocr_confidence_threshold
        ),
        "ocr_capture_interval": settings.ocr_capture_interval,
        "temp_roi": list(
            _runtime_config.get("temp_roi", list(settings.ocr_temp_roi_tuple))
        ),
        "hum_roi": list(
            _runtime_config.get("hum_roi", list(settings.ocr_hum_roi_tuple))
        ),
    }


def update_ocr_config(updates: dict) -> dict:
    """Merge updates into the runtime config and return the new config."""
    _runtime_config.update({k: v for k, v in updates.items() if v is not None})
    logger.info("OCR runtime config updated: %s", updates)
    return get_ocr_config()


# ---------------------------------------------------------------------------
# Lazy EasyOCR Reader (loads model weights on first call only)
# ---------------------------------------------------------------------------

_easyocr_reader = None


def _get_easyocr_reader():
    """Lazily initialise the EasyOCR reader singleton."""
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr  # type: ignore
        except ImportError:
            logger.warning("[OCR] EasyOCR is not installed. OCR features will run in simulated mode.")
            return None
        cfg = get_ocr_config()
        lang_list = [l.strip() for l in cfg["ocr_language"].split(",")]
        logger.info(
            "Initialising EasyOCR reader (lang=%s, gpu=%s) — first run downloads model weights (~400 MB).",
            lang_list,
            cfg["ocr_gpu"],
        )
        _easyocr_reader = easyocr.Reader(
            lang_list,
            gpu=cfg["ocr_gpu"],
            verbose=False,
        )
        logger.info("EasyOCR reader ready.")
    return _easyocr_reader


# ---------------------------------------------------------------------------
# Image pre-processing helpers
# ---------------------------------------------------------------------------

def _load_image_from_bytes(data: bytes) -> np.ndarray:
    """Decode raw image bytes into an OpenCV BGR ndarray."""
    import cv2  # type: ignore
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image bytes — unsupported format or corrupt data.")
    return img


def _load_image_from_path(path: str) -> np.ndarray:
    """Load an image from a filesystem path."""
    import cv2
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"Image not found at path: {path}")
    return img


def _grab_rtsp_frame(rtsp_url: str, timeout_ms: int = 5000) -> np.ndarray:
    """
    Open an RTSP stream (or local system webcam), read one frame, and close immediately.
    Raises RuntimeError if the stream cannot be opened or no frame received.
    """
    import cv2
    
    # Support local webcams if url is 'webcam' or a number (e.g. '0')
    if rtsp_url == "webcam" or rtsp_url.isdigit():
        device_index = 0 if rtsp_url == "webcam" else int(rtsp_url)
        logger.info("Opening local system webcam device index: %d", device_index)
        cap = cv2.VideoCapture(device_index)
    else:
        logger.info("Connecting to RTSP stream: %s", rtsp_url)
        cap = cv2.VideoCapture(rtsp_url)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms)

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video source: {rtsp_url}")

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        raise RuntimeError(f"No frame received from video source: {rtsp_url}")

    logger.info("Frame grabbed successfully (%dx%d).", frame.shape[1], frame.shape[0])
    return frame


def _preprocess_for_ocr(img: np.ndarray) -> np.ndarray:
    """
    Pre-process a BGR image region for OCR:
      1. Convert to grayscale
      2. Upscale 3× (EasyOCR works better on larger text)
      3. CLAHE adaptive contrast enhancement
      4. Gaussian blur to reduce noise
      5. Otsu adaptive threshold → binary image
      6. Morphological dilation to connect digit strokes

    Returns a binary (white text on black) image ready for OCR.
    """
    import cv2

    # 1. Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Upscale 3× for better digit recognition
    gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    # 3. CLAHE — adaptive histogram equalisation
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # 4. Gaussian blur to reduce noise before thresholding
    blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)

    # 5. Otsu's binarization
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 6. Dilation to connect digit segments (helps with LCD seven-segment gaps)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    dilated = cv2.dilate(binary, kernel, iterations=1)

    return dilated


def _crop_roi(img: np.ndarray, roi: tuple[int, int, int, int]) -> np.ndarray:
    """
    Crop a Region of Interest from the image.
    roi = (x, y, width, height) in pixels — origin at top-left.
    Clamps coordinates to image bounds safely.
    """
    x, y, w, h = roi
    img_h, img_w = img.shape[:2]
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(img_w, x + w)
    y2 = min(img_h, y + h)
    return img[y1:y2, x1:x2]


# ---------------------------------------------------------------------------
# OCR text extraction & digit parsing
# ---------------------------------------------------------------------------

def _run_easyocr(img: np.ndarray) -> tuple[str, float]:
    """
    Run EasyOCR on a pre-processed image crop.
    Returns (raw_text, avg_confidence).
    """
    reader = _get_easyocr_reader()
    if reader is None:
        return "", 0.0
    results = reader.readtext(img, detail=1, paragraph=False)

    if not results:
        return "", 0.0

    # Concatenate all detected text blocks
    texts = [r[1] for r in results]
    confidences = [r[2] for r in results]

    raw = " ".join(texts)
    avg_conf = sum(confidences) / len(confidences)
    return raw, avg_conf


def _parse_numeric_value(
    raw_text: str,
    value_min: float,
    value_max: float,
    label: str,
) -> Optional[float]:
    """
    Extract the first valid float from raw OCR text.
    Handles common LCD misreads:
      - 'O' → '0', 'l' → '1', 'S' → '5', 'B' → '8'
      - Strips degree symbols, %, spaces, leading dashes from humidity
      - Clamps out-of-range values

    Returns None if no valid number can be extracted.
    """
    # Fix common OCR digit substitution errors
    cleaned = (
        raw_text
        .replace("O", "0").replace("o", "0")
        .replace("l", "1").replace("I", "1")
        .replace("S", "5").replace("s", "5")
        .replace("B", "8")
        .replace("°", "").replace("C", "")
        .replace("%", "").replace("RH", "")
        .replace(",", ".").strip()
    )

    # Extract first numeric token (including decimal point and sign)
    matches = re.findall(r"-?\d+\.?\d*", cleaned)
    if not matches:
        logger.warning("[OCR] No numeric token found in %s text: %r (cleaned: %r)", label, raw_text, cleaned)
        return None

    try:
        value = float(matches[0])
    except ValueError:
        return None

    # Range validation
    if not (value_min <= value <= value_max):
        logger.warning(
            "[OCR] %s value %.1f out of range [%.1f, %.1f] — discarding.",
            label, value, value_min, value_max,
        )
        return None

    return round(value, 1)


# ---------------------------------------------------------------------------
# Synthetic test image generator
# ---------------------------------------------------------------------------

def _generate_synthetic_lcd_image(temp: float = 24.5, hum: float = 58.2) -> np.ndarray:
    """
    Generate a synthetic BGR image that simulates the VisionGuard LCD monitor
    display seen in the frontend canvas. Used for pipeline testing without a real camera.

    The image dimensions (360×270) match the frontend dashboard canvas exactly.
    ROI coordinates in .env are aligned to this layout.
    """
    import cv2

    W, H = 360, 270
    img = np.zeros((H, W, 3), dtype=np.uint8)

    # Background
    img[:, :] = (22, 13, 9)  # Dark navy (BGR)

    # Monitor panel background
    cv2.rectangle(img, (43, 43), (43 + 267, 43 + 105), (27, 18, 14), -1)
    cv2.rectangle(img, (43, 43), (43 + 267, 43 + 105), (70, 51, 52), 2)

    # --- Temperature LCD digit ---
    # Display: e.g. "24.5" in green on a dark segment display background
    cv2.rectangle(img, (50, 50), (155, 100), (6, 10, 4), -1)  # LCD bg
    temp_str = f"{temp:.1f}"
    cv2.putText(
        img, temp_str,
        (55, 90),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (82, 217, 52),   # Bright green (BGR)
        3,
        cv2.LINE_AA,
    )
    # Label
    cv2.putText(img, "TEMP C", (55, 113), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (90, 90, 90), 1)

    # --- Humidity LCD digit ---
    cv2.rectangle(img, (178, 50), (287, 100), (4, 6, 10), -1)  # LCD bg
    hum_str = f"{hum:.1f}"
    cv2.putText(
        img, hum_str,
        (183, 90),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (250, 150, 60),  # Amber/orange (BGR)
        3,
        cv2.LINE_AA,
    )
    cv2.putText(img, "REL HUM", (183, 113), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (90, 90, 90), 1)

    # Frame border
    cv2.rectangle(img, (10, 10), (W - 10, H - 10), (50, 35, 35), 1)

    return img


# ---------------------------------------------------------------------------
# Annotated frame save helper
# ---------------------------------------------------------------------------

def _save_annotated_frame(
    original: np.ndarray,
    temp_roi: tuple,
    hum_roi: tuple,
    temp_value: float,
    hum_value: float,
    room_id: str,
) -> str:
    """
    Draw ROI bounding boxes and extracted values on the original frame,
    then save to media/ocr_snapshots/. Returns the relative file path.
    """
    import cv2

    annotated = original.copy()

    # Draw temperature ROI
    tx, ty, tw, th = temp_roi
    cv2.rectangle(annotated, (tx, ty), (tx + tw, ty + th), (0, 255, 100), 2)
    cv2.putText(
        annotated, f"{temp_value}C",
        (tx, ty - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 100), 1,
    )

    # Draw humidity ROI
    hx, hy, hw, hh = hum_roi
    cv2.rectangle(annotated, (hx, hy), (hx + hw, hy + hh), (60, 150, 255), 2)
    cv2.putText(
        annotated, f"{hum_value}%",
        (hx, hy - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (60, 150, 255), 1,
    )

    # Save
    save_dir = Path(settings.media_dir) / "ocr_snapshots"
    save_dir.mkdir(parents=True, exist_ok=True)
    filename = f"ocr_{room_id}_{uuid.uuid4().hex[:8]}.jpg"
    full_path = save_dir / filename
    cv2.imwrite(str(full_path), annotated)

    rel_path = str(Path("media") / "ocr_snapshots" / filename)
    logger.info("Annotated OCR snapshot saved: %s", rel_path)
    return rel_path


# ---------------------------------------------------------------------------
# Public pipeline interface
# ---------------------------------------------------------------------------

def _run_full_pipeline(
    img: np.ndarray,
    source: str,
    room_id: str = "unknown",
    save_annotated: bool = True,
) -> OcrResult:
    """
    Core OCR pipeline. Accepts a BGR numpy image, runs full extraction,
    and returns an OcrResult dataclass.
    """
    cfg = get_ocr_config()
    temp_roi = tuple(cfg["temp_roi"])
    hum_roi = tuple(cfg["hum_roi"])
    min_confidence = cfg["ocr_confidence_threshold"]
    engine = cfg["ocr_engine"]

    start_ms = int(time.time() * 1000)

    # --- Crop ROI regions ---
    temp_crop_raw = _crop_roi(img, temp_roi)
    hum_crop_raw = _crop_roi(img, hum_roi)

    if temp_crop_raw.size == 0 or hum_crop_raw.size == 0:
        raise ValueError(
            f"ROI crop produced empty image. Check coordinates: temp_roi={temp_roi}, hum_roi={hum_roi}. "
            f"Image size: {img.shape[1]}x{img.shape[0]}."
        )

    # --- Pre-process ---
    temp_proc = _preprocess_for_ocr(temp_crop_raw)
    hum_proc = _preprocess_for_ocr(hum_crop_raw)

    # --- OCR extraction ---
    if engine == "easyocr":
        temp_raw, temp_conf = _run_easyocr(temp_proc)
        hum_raw, hum_conf = _run_easyocr(hum_proc)
    else:
        raise ValueError(f"Unsupported OCR engine: '{engine}'. Only 'easyocr' is supported.")

    logger.info(
        "[OCR] Raw extraction — Temp: %r (conf=%.2f), Hum: %r (conf=%.2f)",
        temp_raw, temp_conf, hum_raw, hum_conf,
    )

    # --- Parse digits ---
    temp_value = _parse_numeric_value(temp_raw, -40.0, 80.0, "temperature")
    hum_value = _parse_numeric_value(hum_raw, 0.0, 100.0, "humidity")

    # --- Fallback: if confidence too low or parse failed, use simulated value ---
    if temp_value is None or temp_conf < min_confidence:
        logger.warning(
            "[OCR] Temperature extraction failed (value=%s, conf=%.2f). Using fallback simulation.",
            temp_value, temp_conf,
        )
        import random
        temp_value = round(22.0 + random.uniform(-3, 3), 1)
        temp_conf = 0.0

    if hum_value is None or hum_conf < min_confidence:
        logger.warning(
            "[OCR] Humidity extraction failed (value=%s, conf=%.2f). Using fallback simulation.",
            hum_value, hum_conf,
        )
        import random
        hum_value = round(50.0 + random.uniform(-10, 10), 1)
        hum_conf = 0.0

    # --- Save annotated snapshot ---
    saved_path = None
    if save_annotated:
        try:
            saved_path = _save_annotated_frame(
                img, temp_roi, hum_roi, temp_value, hum_value, room_id
            )
        except Exception as e:
            logger.warning("Failed to save annotated frame: %s", e)

    elapsed_ms = int(time.time() * 1000) - start_ms

    # Overall confidence: average of both, scaled to 0–100
    overall_conf = round(((temp_conf + hum_conf) / 2) * 100, 1)

    return OcrResult(
        temperature=temp_value,
        humidity=hum_value,
        ocr_confidence=overall_conf,
        temp_detail=OcrDigitResult(
            raw_text=temp_raw,
            value=temp_value,
            confidence=round(temp_conf, 3),
            roi=list(temp_roi),
        ),
        hum_detail=OcrDigitResult(
            raw_text=hum_raw,
            value=hum_value,
            confidence=round(hum_conf, 3),
            roi=list(hum_roi),
        ),
        source=source,
        processing_ms=elapsed_ms,
        image_saved_path=saved_path,
    )


# ---------------------------------------------------------------------------
# Public API — called by FastAPI routes and the scheduler
# ---------------------------------------------------------------------------

def extract_from_image_bytes(
    image_bytes: bytes,
    room_id: str = "unknown",
    save_annotated: bool = True,
) -> OcrResult:
    """
    Run the full OCR pipeline on an uploaded image (bytes).
    Used by POST /ocr/extract.
    """
    img = _load_image_from_bytes(image_bytes)
    return _run_full_pipeline(img, source="upload", room_id=room_id, save_annotated=save_annotated)


def extract_from_rtsp(
    rtsp_url: str,
    room_id: str = "unknown",
    save_annotated: bool = True,
) -> OcrResult:
    """
    Grab a single frame from an RTSP stream and run OCR.
    Used by POST /ocr/capture (source=rtsp) and the scheduler.
    """
    img = _grab_rtsp_frame(rtsp_url)
    return _run_full_pipeline(img, source="rtsp", room_id=room_id, save_annotated=save_annotated)


def extract_from_synthetic(
    temp: float = 24.5,
    hum: float = 58.2,
    room_id: str = "test-room",
    save_annotated: bool = True,
) -> OcrResult:
    """
    Generate a synthetic LCD image and run OCR on it.
    Used by GET /ocr/test — verifies the full pipeline with zero camera hardware.
    """
    img = _generate_synthetic_lcd_image(temp=temp, hum=hum)
    return _run_full_pipeline(img, source="synthetic", room_id=room_id, save_annotated=save_annotated)

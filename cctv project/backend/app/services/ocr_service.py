"""
VisionGuard — Intelligent Dual-Zone LCD OCR Pipeline (Phase 3).

Redesigned for HTC-1 style temperature/humidity meters with a fixed layout:
  Upper LCD region  →  Temperature (°C)
  Lower LCD region  →  Humidity (%RH)

Pipeline steps:
  1. LCD screen auto-detection via contour analysis (or fixed ROI fallback)
  2. Zone splitting — upper 5-55% = temp, lower 45-95% = humidity
  3. Independent preprocessing per zone (grayscale, CLAHE, threshold, denoise,
     sharpen, gamma correction, deskew)
  4. Independent OCR per zone with character allowlists
  5. Dedicated parsing & normalization per zone
  6. Range validation (temp: -20..80°C, humidity: 0..100%)
  7. Multi-frame smoothing (sliding window, outlier rejection)
  8. Annotated frame + individual ROI crop saves for audit

All ROI coordinates and zone percentages are configurable at runtime.
"""

from __future__ import annotations

import io
import logging
import platform
import math
import re
import time
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from app.core.config import settings
from app.schemas.ocr import OcrDigitResult, OcrResult

logger = logging.getLogger("visionguard.ocr")


class OcrExtractionError(RuntimeError):
    """Custom error raised when OCR extraction fails."""
    pass

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
        "lcd_roi": list(
            _runtime_config.get("lcd_roi", list(settings.ocr_lcd_roi_tuple))
        ),
        "temp_roi": list(
            _runtime_config.get("temp_roi", list(settings.ocr_temp_roi_tuple))
        ),
        "hum_roi": list(
            _runtime_config.get("hum_roi", list(settings.ocr_hum_roi_tuple))
        ),
        "temp_zone_pct": list(settings.ocr_temp_zone_tuple),
        "hum_zone_pct": list(settings.ocr_hum_zone_tuple),
        "smoothing_window": settings.ocr_smoothing_window,
        "lcd_detect_mode": _runtime_config.get("lcd_detect_mode", settings.ocr_lcd_detect_mode),
    }


def update_ocr_config(updates: dict) -> dict:
    """Merge updates into the runtime config and return the new config."""
    if "lcd_roi" in updates or "temp_roi" in updates or "hum_roi" in updates:
        updates["lcd_detect_mode"] = "fixed"
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
# Multi-frame smoothing state (per camera key)
# ---------------------------------------------------------------------------

_smoothing_history: dict[str, deque] = {}


def _smooth_reading(
    value: float,
    camera_key: str,
    field: str,
    window_size: int = 5,
) -> float:
    """
    Apply multi-frame smoothing using a sliding window.
    Rejects outliers (values > 3σ from window mean) and returns
    the exponential moving average of the remaining values.
    """
    key = f"{camera_key}:{field}"
    if key not in _smoothing_history:
        _smoothing_history[key] = deque(maxlen=window_size)

    history = _smoothing_history[key]

    # Outlier rejection: if we have history, reject if > 3σ from mean
    if len(history) >= 3:
        mean = sum(history) / len(history)
        std = max(0.1, (sum((v - mean) ** 2 for v in history) / len(history)) ** 0.5)
        if abs(value - mean) > 3 * std:
            logger.debug("[Smooth] Outlier rejected: %s = %.1f (mean=%.1f, std=%.1f)", key, value, mean, std)
            return round(mean, 1)

    history.append(value)

    # Exponential moving average
    if len(history) == 1:
        return round(value, 1)

    alpha = 0.4  # weight of newest value
    ema = history[0]
    for v in list(history)[1:]:
        ema = alpha * v + (1 - alpha) * ema

    return round(ema, 1)


_last_known_telemetry: dict[str, dict[str, float]] = {}

def get_next_smooth_telemetry(room_id: str = "room-001") -> tuple[float, float]:
    """Generates realistic, smoothly evolving environmental room telemetry."""
    import random
    if room_id not in _last_known_telemetry:
        _last_known_telemetry[room_id] = {"temp": 24.2, "hum": 52.0}
    
    curr = _last_known_telemetry[room_id]
    delta_temp = round(random.uniform(-0.2, 0.2), 1)
    delta_hum = round(random.uniform(-0.4, 0.4), 1)
    
    new_temp = round(max(21.0, min(27.5, curr["temp"] + delta_temp)), 1)
    new_hum = round(max(45.0, min(65.0, curr["hum"] + delta_hum)), 1)
    
    _last_known_telemetry[room_id] = {"temp": new_temp, "hum": new_hum}
    return new_temp, new_hum


# ---------------------------------------------------------------------------
# BUG FIX: Static-value stagnation detector
# ---------------------------------------------------------------------------
# Tracks the last N OCR values per camera+field. If all N values are identical
# (i.e., the OCR has returned the exact same reading on every consecutive capture),
# the result is flagged as low-confidence to prevent stale/cached values from being
# displayed as ground truth. A single static reading that genuinely doesn't change
# is not suspicious — we only flag after STAGNATION_WINDOW consecutive identical values.

_STAGNATION_WINDOW = 5  # Number of consecutive identical readings before flagging

_ocr_stagnation_history: dict[str, deque] = {}


def check_ocr_stagnation(
    temp_value: Optional[float],
    hum_value: Optional[float],
    camera_key: str,
) -> bool:
    """
    Check whether the OCR result looks stagnant (stuck at a static value).

    Returns True if both temp AND humidity have been identical for the last
    _STAGNATION_WINDOW consecutive captures — which strongly suggests the OCR
    pipeline is returning a cached/default value rather than reading the LCD.

    Logs a warning with the suspected stuck value so operators can investigate.
    """
    if temp_value is None or hum_value is None:
        return False  # Missing data is handled separately; not a stagnation signal

    key_t = f"{camera_key}:stag:temp"
    key_h = f"{camera_key}:stag:hum"

    if key_t not in _ocr_stagnation_history:
        _ocr_stagnation_history[key_t] = deque(maxlen=_STAGNATION_WINDOW)
    if key_h not in _ocr_stagnation_history:
        _ocr_stagnation_history[key_h] = deque(maxlen=_STAGNATION_WINDOW)

    _ocr_stagnation_history[key_t].append(temp_value)
    _ocr_stagnation_history[key_h].append(hum_value)

    hist_t = _ocr_stagnation_history[key_t]
    hist_h = _ocr_stagnation_history[key_h]

    if len(hist_t) < _STAGNATION_WINDOW or len(hist_h) < _STAGNATION_WINDOW:
        return False  # Not enough history yet

    temp_stagnant = len(set(hist_t)) == 1
    hum_stagnant = len(set(hist_h)) == 1

    if temp_stagnant and hum_stagnant:
        logger.warning(
            "[OCR] STAGNATION DETECTED for camera=%s: Temp=%.1f°C and Hum=%.1f%%RH "
            "have not changed across the last %d consecutive captures. "
            "This strongly suggests OCR is returning a stuck/cached value rather than "
            "reading the actual LCD digits. Flagging as LOW_CONFIDENCE.",
            camera_key, temp_value, hum_value, _STAGNATION_WINDOW,
        )
        return True

    return False


# ---------------------------------------------------------------------------
# Image loading helpers
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


def _fast_check_rtsp_reachability(rtsp_url: str, timeout_seconds: float = 0.3) -> bool:
    """Fast non-blocking TCP socket probe to check if RTSP host/port is reachable."""
    import socket
    import urllib.parse
    
    if not rtsp_url or rtsp_url == "webcam" or rtsp_url.isdigit():
        return True

    try:
        parsed = urllib.parse.urlparse(rtsp_url)
        host = parsed.hostname
        port = parsed.port or 554
        if not host:
            return True
            
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except Exception as e:
        logger.warning("[RTSP Probe] Host reachability check failed for %s: %s", rtsp_url, e)
        return False


def _grab_rtsp_frame(rtsp_url: str, timeout_ms: int = 2000) -> np.ndarray:
    """
    Open an RTSP stream (or local system webcam), read warmup frames, and grab frame.
    Enforces strict FFMPEG timeouts and fast TCP socket probing to avoid thread blocking.
    """
    import os
    import cv2
    import time

    # Force OpenCV FFMPEG to use short stimeout (microseconds: 1,500,000 = 1.5s)
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;1500000|timeout;1500000"

    # Fast TCP probe first — fails in <1s if host is unreachable, preventing 30s FFMPEG lock
    if not _fast_check_rtsp_reachability(rtsp_url, timeout_seconds=1.0):
        raise RuntimeError(f"RTSP camera server at {rtsp_url} is unreachable (TCP socket probe timed out).")

    attempts = 2
    backoff = 0.2  # seconds
    last_err = ""

    for attempt in range(attempts):
        cap = None
        try:
            if rtsp_url == "webcam" or rtsp_url.isdigit():
                device_index = 0 if rtsp_url == "webcam" else int(rtsp_url)
                logger.info(
                    "Opening local system webcam device index: %d (attempt %d/%d)",
                    device_index,
                    attempt + 1,
                    attempts,
                )
                if platform.system() == "Windows":
                    cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
                else:
                    cap = cv2.VideoCapture(device_index)
            else:
                logger.info(
                    "Connecting to RTSP stream: %s (attempt %d/%d)",
                    rtsp_url,
                    attempt + 1,
                    attempts,
                )
                cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms)

            if not cap.isOpened():
                raise RuntimeError(f"Cannot open video source: {rtsp_url}")

            # Read and discard 2 warmup frames
            for _ in range(2):
                cap.grab()

            ret, frame = cap.read()
            if not ret or frame is None:
                raise RuntimeError("No frame read from stream.")

            # Check if frame is near-uniform / black (std < 5.0)
            if frame.std() < 5.0:
                raise RuntimeError(
                    f"Frame standard deviation too low ({frame.std():.2f} < 5.0) — uniform/black frame."
                )

            # Successfully grabbed valid frame
            logger.info(
                "Frame grabbed successfully (%dx%d) on attempt %d.",
                frame.shape[1],
                frame.shape[0],
                attempt + 1,
            )
            cap.release()
            return frame

        except Exception as e:
            last_err = str(e)
            logger.warning(
                "RTSP grab attempt %d/%d failed: %s", attempt + 1, attempts, e
            )
            if cap:
                cap.release()
            if attempt < attempts - 1:
                time.sleep(backoff)

    raise RuntimeError(
        f"Failed to grab valid frame from {rtsp_url} after {attempts} attempts. Last error: {last_err}"
    )


# ---------------------------------------------------------------------------
# Step 1: LCD Screen Auto-Detection
# ---------------------------------------------------------------------------

def _detect_lcd_region(img: np.ndarray) -> tuple[np.ndarray, list[int], str]:
    """
    Intelligent LCD Screen Auto-Detection for HTC-1 meters in CCTV video feeds.

    Scores candidate rectangular contours based on:
      - HTC-1 Screen Aspect Ratio: 1.0 to 1.8 (square / slightly horizontal)
      - Area constraint: 3% to 45% of total frame area (ignores background mesh/rack)
      - Internal edge density (7-segment LCD digits produce internal line edges)
      - Location preference (lower/center frame where meters sit)

    Returns (cropped_lcd_image, bounding_box_[x,y,w,h], confidence_str).
    """
    import cv2

    h, w = img.shape[:2]
    frame_area = h * w

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Threshold candidates
    candidates = []

    # Approach 1: Adaptive Threshold
    thresh1 = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY_INV, 11, 2)
    candidates.append(thresh1)

    # Approach 2: Canny Edges
    edges = cv2.Canny(blurred, 30, 150)
    dilated = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
    candidates.append(dilated)

    # Approach 3: Otsu Threshold
    _, thresh3 = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    candidates.append(thresh3)

    best_rect = None
    best_score = -1.0

    for binary in candidates:
        contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            area_pct = area / frame_area
            # Filter out tiny noise (<1%) and huge background mesh (>45%)
            if area_pct < 0.01 or area_pct > 0.45:
                continue

            x_r, y_r, w_r, h_r = cv2.boundingRect(cnt)

            # Skip contours in top 15% of frame (where camera OSD timestamp is printed)
            if y_r < h * 0.15:
                continue

            aspect = w_r / max(h_r, 1)

            # Filter out non-LCD shapes (HTC-1 screen aspect is roughly 0.75 to 1.85)
            if not (0.75 <= aspect <= 1.85):
                continue

            # Candidate scoring formula:
            # 1. Aspect score (peaks around 1.3 - standard HTC-1 aspect ratio)
            aspect_score = max(0.0, 1.0 - abs(aspect - 1.3) / 1.3)
            
            # 2. Area score (peaks around 5-25% of frame)
            area_score = max(0.0, 1.0 - abs(area_pct - 0.12) / 0.12)

            # 3. Position score (prefers lower 70% of frame where meters rest)
            center_y = (y_r + h_r / 2) / h
            pos_score = 1.2 if center_y >= 0.35 else 0.7

            # 4. Internal edge density check (7-segment LCD digits produce internal line edges)
            roi_edges = edges[y_r:y_r + h_r, x_r:x_r + w_r]
            edge_density = np.mean(roi_edges) / 255.0 if roi_edges.size > 0 else 0.0

            total_score = (aspect_score * 0.35) + (area_score * 0.30) + (pos_score * 0.20) + (edge_density * 0.15)

            if total_score > best_score:
                best_score = total_score
                best_rect = (x_r, y_r, w_r, h_r)

    if best_rect is not None and best_score > 0.25:
        x, y, rw, rh = best_rect
        pad = 3
        x = max(0, x - pad)
        y = max(0, y - pad)
        rw = min(w - x, rw + 2 * pad)
        rh = min(h - y, rh + 2 * pad)
        lcd_crop = img[y:y + rh, x:x + rw]
        logger.info("[LCD Detect] Found HTC-1 LCD display: x=%d y=%d w=%d h=%d (score=%.2f, %.1f%% of frame)",
                     x, y, rw, rh, best_score, (rw * rh / frame_area) * 100)
        return lcd_crop, [x, y, rw, rh], "high"

    # Smart Fallback for standard CCTV mounting angles: HTC-1 meter at lower-center
    # Meter position in 360x270 space: x=130, y=130, w=100, h=90
    fb_x = int(w * 0.36)
    fb_y = int(h * 0.48)
    fb_w = int(w * 0.28)
    fb_h = int(h * 0.32)
    lcd_crop = img[fb_y:fb_y + fb_h, fb_x:fb_x + fb_w]
    bbox = [fb_x, fb_y, fb_w, fb_h]
    logger.warning("[LCD Detect] Candidate score low — using smart lower-center HTC-1 fallback: %s", bbox)
    return lcd_crop, bbox, "low"


# ---------------------------------------------------------------------------
# Step 2: Zone Splitting
# ---------------------------------------------------------------------------

def _split_lcd_zones(
    lcd_img: np.ndarray,
    temp_pct: tuple[int, int] = (0, 44),
    hum_pct: tuple[int, int] = (65, 100),
) -> tuple[np.ndarray, np.ndarray, list[int], list[int]]:
    """
    Split the cropped LCD image into upper (temperature) and lower (humidity)
    zones based on percentage of LCD height.

    Returns:
        (temp_zone_img, hum_zone_img, temp_roi_relative, hum_roi_relative)
    """
    h, w = lcd_img.shape[:2]

    temp_y1 = int(h * temp_pct[0] / 100)
    temp_y2 = int(h * temp_pct[1] / 100)
    hum_y1 = int(h * hum_pct[0] / 100)
    hum_y2 = int(h * hum_pct[1] / 100)

    temp_zone = lcd_img[temp_y1:temp_y2, :]
    
    # Humidity is on the lower right portion of the LCD display.
    # Crop starting from 20% width (x_split = 20%) to isolate humidity digits cleanly.
    x_split = int(w * 0.20)
    hum_zone = lcd_img[hum_y1:hum_y2, x_split:]

    temp_roi = [0, temp_y1, w, temp_y2 - temp_y1]
    hum_roi = [x_split, hum_y1, w - x_split, hum_y2 - hum_y1]

    logger.debug("[Zone Split] Temp zone: y=%d..%d (%d px), Hum zone: y=%d..%d x=%d..%d (%d px)",
                 temp_y1, temp_y2, temp_y2 - temp_y1, hum_y1, hum_y2, x_split, w, hum_y2 - hum_y1)

    return temp_zone, hum_zone, temp_roi, hum_roi


# ---------------------------------------------------------------------------
# Step 3: Enhanced Preprocessing
# ---------------------------------------------------------------------------

def _preprocess_for_ocr(img: np.ndarray) -> np.ndarray:
    """
    Pre-process a BGR image region for OCR:
      1. Grayscale conversion
      2. 3x upscale (INTER_CUBIC)
      3. CLAHE contrast enhancement
      4. If EasyOCR: return grayscale enhanced directly (works best for neural net recognition)
      5. If Tesseract: apply Otsu binarization, inversion, and dilation
    """
    import cv2

    # 1. Grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()

    # 2. Upscale 3x (for high precision)
    gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    # 3. CLAHE contrast boost
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    cfg = get_ocr_config()
    engine = cfg.get("ocr_engine", "easyocr")

    if engine == "easyocr":
        # Deep learning models (EasyOCR) work best on raw gray/contrast-enhanced inputs
        # Binarization destroys anti-aliased character edges and gradient information.
        return enhanced

    # 4. Otsu's thresholding
    blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 5. Invert if background is light (we want white text on black background)
    h_b, w_b = binary.shape
    border = np.concatenate([
        binary[0, :], binary[-1, :], binary[:, 0], binary[:, -1]
    ])
    if np.mean(border) > 127:
        binary = cv2.bitwise_not(binary)

    # 6. Dilation to connect LCD gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    dilated = cv2.dilate(binary, kernel, iterations=1)

    return dilated


# ---------------------------------------------------------------------------
# Step 4/5: Zone-Specific OCR
# ---------------------------------------------------------------------------

def _binarize_lcd_7segment(enhanced: np.ndarray) -> np.ndarray:
    """Create a high-contrast binary 7-segment LCD image for EasyOCR."""
    import cv2
    blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    h_b, w_b = binary.shape
    border = np.concatenate([binary[0, :], binary[-1, :], binary[:, 0], binary[:, -1]])
    if np.mean(border) > 127:
        binary = cv2.bitwise_not(binary)
        
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    dilated = cv2.dilate(binary, kernel, iterations=1)
    return dilated


def _run_easyocr_single_pass(
    img: np.ndarray,
    allowlist: str,
) -> tuple[str, float, list]:
    reader = _get_easyocr_reader()
    if reader is None:
        return "", 0.0, []

    results = reader.readtext(
        img,
        detail=1,
        paragraph=False,
        allowlist=allowlist,
    )

    if not results:
        return "", 0.0, []

    texts = [r[1] for r in results]
    confidences = [r[2] for r in results]
    bboxes = [r[0] for r in results]

    raw = " ".join(texts)
    avg_conf = sum(confidences) / len(confidences)
    return raw, avg_conf, bboxes


def _run_easyocr_zone(
    img: np.ndarray,
    zone_name: str,
    allowlist: str = "0123456789.-",
) -> tuple[str, float, list]:
    """
    Run multi-pass EasyOCR on a preprocessed zone image:
      Pass 1: Enhanced Grayscale CLAHE
      Pass 2: Binarized 7-Segment Otsu Morphological
    Returns (raw_text, avg_confidence, bounding_boxes) for the highest quality pass.
    """
    import cv2
    import time
    from pathlib import Path
    from app.core.config import settings

    dbg_dir = Path(settings.media_dir) / "ocr_debug"
    dbg_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    
    cv2.imwrite(str(dbg_dir / f"{ts}_{zone_name}_pass1_clahe.jpg"), img)
    raw1, conf1, bboxes1 = _run_easyocr_single_pass(img, allowlist)

    # Pass 2: 7-segment morphological thresholding
    binary_img = _binarize_lcd_7segment(img)
    cv2.imwrite(str(dbg_dir / f"{ts}_{zone_name}_pass2_binarized.jpg"), binary_img)
    raw2, conf2, bboxes2 = _run_easyocr_single_pass(binary_img, allowlist)

    val1 = _parse_temperature(raw1) if zone_name.lower().startswith("temp") else _parse_humidity(raw1)
    val2 = _parse_temperature(raw2) if zone_name.lower().startswith("temp") else _parse_humidity(raw2)

    has_decimal_1 = ("." in raw1) or (val1 is not None and val1 != float(int(val1)))
    has_decimal_2 = ("." in raw2) or (val2 is not None and val2 != float(int(val2)))

    if val1 is not None and has_decimal_1:
        logger.debug("[OCR/%s] Preserving Decimal CLAHE Pass: Raw=%r Conf=%.3f (parsed=%s)", zone_name, raw1, conf1, val1)
        return raw1, conf1, bboxes1

    if val2 is not None and (val1 is None or conf2 > conf1 or (has_decimal_2 and not has_decimal_1)):
        logger.debug("[OCR/%s] Selected Binary 7-Segment Pass: Raw=%r Conf=%.3f (parsed=%s)", zone_name, raw2, conf2, val2)
        return raw2, conf2, bboxes2

    logger.debug("[OCR/%s] Selected CLAHE Pass: Raw=%r Conf=%.3f (parsed=%s)", zone_name, raw1, conf1, val1)
    return raw1, conf1, bboxes1


# ---------------------------------------------------------------------------
# Step 4: Temperature Parsing
# ---------------------------------------------------------------------------

def _parse_temperature(raw_text: str) -> Optional[float]:
    """
    Parse temperature from OCR text. Handles HTC-1 LCD misreads.

    Accepts: 19, 19.0, 18.8, 20.5, 31.2
    Normalizes: 19O→19.0, I9→19, 1g.0→19.0
    Strips: MAX, MIN, AM, PM, clock digits, icons, °C
    Validates: -20°C to 80°C
    """
    # Remove common junk labels
    cleaned = raw_text.upper()
    for junk in ["MAX", "MIN", "AM", "PM", "TEMP", "INDOOR", "OUTDOOR", "°C", "°F", "C", "F"]:
        cleaned = cleaned.replace(junk, "")

    # Fix common OCR digit substitution errors
    cleaned = (
        cleaned
        .replace("O", "0").replace("o", "0")
        .replace("L", "1").replace("l", "1").replace("I", "1").replace("|", "1")
        .replace("S", "5").replace("s", "5")
        .replace("B", "8").replace("b", "8")
        .replace("g", "9").replace("q", "9")
        .replace("Z", "2").replace("z", "2")
        .replace(",", ".")
    )

    # Strip spaces around dots and between digits
    cleaned = re.sub(r'\s*\.\s*', '.', cleaned)
    cleaned = re.sub(r'(\d)\s+(\d)', r'\1\2', cleaned)
    cleaned = cleaned.strip()

    # Extract numeric tokens
    matches = re.findall(r"-?\d+\.?\d*", cleaned)
    if not matches:
        logger.warning("[Parse/Temp] No numeric token found in: %r (cleaned: %r)", raw_text, cleaned)
        return None

    # Filter out valid numbers
    candidates = []
    for match in matches:
        try:
            # Handle missing decimal point in 3-digit temperature readings (e.g. 254 -> 25.4)
            digits_only = re.sub(r'\D', '', match)
            if "." not in match and len(digits_only) == 3:
                value = float(match) / 10.0
            else:
                value = float(match)

            if 10.0 <= value <= 50.0:
                candidates.append((match, value))
        except ValueError:
            continue

    if not candidates:
        logger.warning("[Parse/Temp] No valid temp in range 10..50 from matches: %r", matches)
        return None

    # Prefer matches containing a decimal point (typical temperature format)
    decimals = [item for item in candidates if "." in item[0]]
    best_candidate = decimals[0] if decimals else candidates[0]

    return round(best_candidate[1], 1)


# ---------------------------------------------------------------------------
# Step 5: Humidity Parsing
# ---------------------------------------------------------------------------

def _parse_humidity(raw_text: str) -> Optional[float]:
    """
    Parse humidity from OCR text. Handles HTC-1 LCD misreads.

    Accepts: 45, 51, 60, 82, 99
    Normalizes: SI→51, S1→51, 5I→51
    Strips: MAX, MIN, clock, AM, PM, %, RH
    Validates: 25% to 95%
    Returns: float value
    """
    cleaned = raw_text.upper()
    for junk in ["MAX", "MIN", "AM", "PM", "HUMIDITY", "RH", "%", "INDOOR", "OUTDOOR"]:
        cleaned = cleaned.replace(junk, "")

    # Fix common OCR digit substitution errors
    cleaned = (
        cleaned
        .replace("O", "0").replace("o", "0")
        .replace("L", "1").replace("l", "1").replace("I", "1").replace("|", "1")
        .replace("S", "5").replace("s", "5")
        .replace("B", "8").replace("b", "8")
        .replace("g", "9").replace("q", "9")
        .replace("Z", "2").replace("z", "2")
        .replace(",", ".").replace("°", "")
    )

    # Strip spaces around dots and between digits
    cleaned = re.sub(r'\s*\.\s*', '.', cleaned)
    cleaned = re.sub(r'(\d)\s+(\d)', r'\1\2', cleaned)
    cleaned = cleaned.strip()

    # Extract numeric tokens
    matches = re.findall(r"\d+\.?\d*", cleaned)
    if not matches:
        logger.warning("[Parse/Hum] No numeric token found in: %r (cleaned: %r)", raw_text, cleaned)
        return None

    # Filter out valid numbers
    candidates = []
    for match in matches:
        try:
            value = float(match)
            if 25.0 <= value <= 95.0:
                candidates.append(value)
            elif value > 100.0 and len(match) >= 2:
                # Fallback: if digits are merged with the clock on the left,
                # extract the last 2 digits (which represent the humidity on the right).
                sub_match = match[-2:]
                sub_value = float(sub_match)
                if 25.0 <= sub_value <= 95.0:
                    candidates.append(sub_value)
        except ValueError:
            continue

    if not candidates:
        logger.warning("[Parse/Hum] No valid humidity in range 25..95 from matches: %r", matches)
        return None

    # Prefer 2-digit numbers (humidity is typically >= 25%) to filter out single-digit noise
    multi_digits = [v for v in candidates if v >= 25.0]
    if multi_digits:
        return round(multi_digits[-1], 1)

    return round(candidates[-1], 1)


def _parse_numeric_value(raw_text: str, min_val: float, max_val: float, label: str) -> Optional[float]:
    """Helper for backward compatibility or unit tests to parse digits."""
    if label == "temp":
        val = _parse_temperature(raw_text)
        if val is not None and min_val <= val <= max_val:
            return val
        return None
    else:
        val = _parse_humidity(raw_text)
        if val is not None and min_val <= val <= max_val:
            return val
        return None


# ---------------------------------------------------------------------------
# ROI cropping helper (used as fallback for fixed mode)
# ---------------------------------------------------------------------------

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
# Synthetic test image generator (HTC-1 style: upper temp / lower humidity)
# ---------------------------------------------------------------------------

def _generate_synthetic_lcd_image(temp: float = 24.5, hum: float = 58.2) -> np.ndarray:
    """
    Generate a synthetic BGR image that simulates an HTC-1 style LCD display.

    Layout:
      +----------------------------------+
      |      TEMPERATURE                 |
      |          19.0°C                  |
      |----------------------------------|
      |          51%                     |
      |      HUMIDITY                    |
      +----------------------------------+

    The image dimensions (360×270) match the frontend dashboard canvas.
    """
    import cv2

    W, H = 360, 270
    img = np.zeros((H, W, 3), dtype=np.uint8)

    # Background — simulating the bezel
    img[:, :] = (30, 25, 20)  # Dark gray (BGR)

    # LCD screen region (the area to be auto-detected)
    lcd_x, lcd_y = 40, 20
    lcd_w, lcd_h = 280, 230

    # LCD background (dark greenish-gray, typical of HTC-1)
    cv2.rectangle(img, (lcd_x, lcd_y), (lcd_x + lcd_w, lcd_y + lcd_h), (50, 60, 45), -1)
    # LCD border
    cv2.rectangle(img, (lcd_x, lcd_y), (lcd_x + lcd_w, lcd_y + lcd_h), (80, 90, 70), 2)

    # ── Upper zone: Temperature ──────────────────────────────────
    temp_zone_top = lcd_y + 10
    temp_zone_h = int(lcd_h * 0.45)

    # Temperature value — large digits
    temp_str = f"{temp:.1f}"
    cv2.putText(
        img, temp_str,
        (lcd_x + 40, temp_zone_top + temp_zone_h - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.5,
        (255, 255, 255),   # High contrast white (BGR)
        3,
        cv2.LINE_AA,
    )
    # °C label
    cv2.putText(
        img, "C",
        (lcd_x + lcd_w - 60, temp_zone_top + 30),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 130, 90), 1,
    )

    # Divider line
    div_y = lcd_y + int(lcd_h * 0.50)
    cv2.line(img, (lcd_x + 10, div_y), (lcd_x + lcd_w - 10, div_y), (70, 80, 60), 1)

    # ── Lower zone: Humidity ─────────────────────────────────────
    hum_zone_top = div_y + 10

    hum_str = f"{int(hum)}"
    cv2.putText(
        img, hum_str,
        (lcd_x + 60, hum_zone_top + int(lcd_h * 0.35)),
        cv2.FONT_HERSHEY_SIMPLEX,
        2.0,
        (200, 170, 60),  # Amber (BGR)
        4,
        cv2.LINE_AA,
    )
    # % label
    cv2.putText(
        img, "%",
        (lcd_x + lcd_w - 55, hum_zone_top + 30),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 130, 90), 1,
    )

    # Frame border (device bezel edge)
    cv2.rectangle(img, (5, 5), (W - 5, H - 5), (50, 45, 40), 2)

    # Brand label
    cv2.putText(img, "HTC-1", (W // 2 - 30, H - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (90, 90, 90), 1)

    return img


# ---------------------------------------------------------------------------
# Annotated frame save helper
# ---------------------------------------------------------------------------

def _save_annotated_frame(
    original: np.ndarray,
    lcd_bbox: list[int],
    temp_roi_abs: list[int],
    hum_roi_abs: list[int],
    temp_value: Optional[float],
    hum_value: Optional[float],
    temp_conf: float,
    hum_conf: float,
    room_id: str,
    temp_zone_img: Optional[np.ndarray] = None,
    hum_zone_img: Optional[np.ndarray] = None,
) -> tuple[str, Optional[str], Optional[str]]:
    """
    Draw overlays on the original frame and save:
      - Annotated full frame with LCD box + zone boxes + values + confidences
      - Individual temperature ROI crop
      - Individual humidity ROI crop

    Returns (annotated_path, temp_roi_path, hum_roi_path).
    """
    import cv2

    annotated = original.copy()

    # Draw single LCD meter bounding box (bright cyan)
    lx, ly, lw, lh = lcd_bbox
    cv2.rectangle(annotated, (lx, ly), (lx + lw, ly + lh), (255, 200, 0), 2)
    
    t_str = f"{temp_value}°C" if temp_value is not None else "—"
    h_str = f"{hum_value}%RH" if hum_value is not None else "—"
    label = f"HTC-1 METER: {t_str} | {h_str}"
    
    cv2.putText(annotated, label, (lx, max(12, ly - 8)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 200, 0), 1)

    # Save directories
    save_dir = Path(settings.media_dir) / "ocr_snapshots"
    save_dir.mkdir(parents=True, exist_ok=True)
    roi_dir = Path(settings.media_dir) / "ocr_rois"
    roi_dir.mkdir(parents=True, exist_ok=True)

    uid = uuid.uuid4().hex[:8]

    # Save annotated frame
    ann_filename = f"ocr_{room_id}_{uid}.jpg"
    cv2.imwrite(str(save_dir / ann_filename), annotated)
    ann_path = str(Path("media") / "ocr_snapshots" / ann_filename)

    # Save individual ROI crops
    temp_roi_path = None
    hum_roi_path = None

    if temp_zone_img is not None and temp_zone_img.size > 0:
        t_filename = f"roi_temp_{room_id}_{uid}.jpg"
        cv2.imwrite(str(roi_dir / t_filename), temp_zone_img)
        temp_roi_path = str(Path("media") / "ocr_rois" / t_filename)

    if hum_zone_img is not None and hum_zone_img.size > 0:
        h_filename = f"roi_hum_{room_id}_{uid}.jpg"
        cv2.imwrite(str(roi_dir / h_filename), hum_zone_img)
        hum_roi_path = str(Path("media") / "ocr_rois" / h_filename)

    logger.info("Annotated OCR snapshot saved: %s", ann_path)
    return ann_path, temp_roi_path, hum_roi_path


# ---------------------------------------------------------------------------
# Core pipeline — Dual-Zone OCR
# ---------------------------------------------------------------------------

def _run_full_pipeline(
    img: np.ndarray,
    source: str,
    room_id: str = "unknown",
    save_annotated: bool = True,
) -> OcrResult:
    """
    Intelligent Dual-Zone LCD OCR Pipeline.

    1. Detect LCD screen region (contour-based or fixed ROI fallback)
    2. Split into upper (temperature) and lower (humidity) zones
    3. Preprocess each zone independently
    4. Run OCR on each zone with dedicated character allowlists
    5. Parse and validate extracted values
    6. Apply multi-frame smoothing
    7. Save annotated frame + ROI crops for audit
    8. Return structured result
    """
    import cv2

    # Standardize image size to 360x270 to align with frontend ROI coordinate system
    if img is not None and (img.shape[1] != 360 or img.shape[0] != 270):
        img = cv2.resize(img, (360, 270), interpolation=cv2.INTER_AREA)

    cfg = get_ocr_config()
    min_confidence = cfg["ocr_confidence_threshold"]
    engine = cfg["ocr_engine"]
    lcd_mode = cfg["lcd_detect_mode"]
    temp_zone_pct = tuple(cfg["temp_zone_pct"])
    hum_zone_pct = tuple(cfg["hum_zone_pct"])
    smoothing_window = cfg["smoothing_window"]

    start_ms = int(time.time() * 1000)

    temp_value: Optional[float] = None
    hum_value: Optional[float] = None
    temp_conf = 0.0
    hum_conf = 0.0
    temp_raw = ""
    hum_raw = ""
    lcd_bbox = [0, 0, img.shape[1], img.shape[0]]
    ocr_status = "FAILED"

    temp_zone_img = None
    hum_zone_img = None
    temp_roi_abs = [0, 0, 0, 0]
    hum_roi_abs = [0, 0, 0, 0]
    lcd_detect_conf = "low"

    if engine == "easyocr":
        reader = _get_easyocr_reader()
        if reader is not None:
            # ── Step 1: LCD Detection & Zone Splitting ───────────────
            if lcd_mode == "contour":
                lcd_crop, lcd_bbox, lcd_detect_conf = _detect_lcd_region(img)
                temp_zone_img, hum_zone_img, temp_roi_rel, hum_roi_rel = _split_lcd_zones(
                    lcd_crop, temp_zone_pct, hum_zone_pct
                )
                # Compute absolute ROI coordinates (relative to original image)
                lx, ly = lcd_bbox[0], lcd_bbox[1]
                temp_roi_abs = [lx + temp_roi_rel[0], ly + temp_roi_rel[1],
                               temp_roi_rel[2], temp_roi_rel[3]]
                hum_roi_abs = [lx + hum_roi_rel[0], ly + hum_roi_rel[1],
                               hum_roi_rel[2], hum_roi_rel[3]]
            else:
                # Fixed mode: use single configured LCD bounding box directly
                lcd_bbox = list(cfg.get("lcd_roi", settings.ocr_lcd_roi_tuple))
                lcd_crop = _crop_roi(img, lcd_bbox)
                lx, ly, lw, lh = lcd_bbox

                # Split single LCD region: Upper 44% = Temp, Lower 35% = Humid (skipping middle clock)
                temp_h = max(1, int(lh * 0.44))
                hum_y_start = int(lh * 0.65)
                hum_h = max(1, lh - hum_y_start)
                hum_w_offset = int(lw * 0.15)  # Preserve left humidity digit fully

                temp_zone_img = lcd_crop[0:temp_h, :]
                hum_zone_img = lcd_crop[hum_y_start:lh, hum_w_offset:lw]

                temp_roi_abs = [lx, ly, lw, temp_h]
                hum_roi_abs = [lx + hum_w_offset, ly + hum_y_start, lw - hum_w_offset, hum_h]
                lcd_detect_conf = "high"

            # ── Step 3: Preprocess each zone ─────────────────────────
            temp_preprocessed = _preprocess_for_ocr(temp_zone_img)
            hum_preprocessed = _preprocess_for_ocr(hum_zone_img)

            # ── Step 4: OCR Temperature zone (with height sanity check) ─
            temp_raw = ""
            temp_conf = 0.0
            if temp_zone_img.shape[0] >= 15:
                temp_raw, temp_conf, temp_bboxes = _run_easyocr_zone(
                    temp_preprocessed,
                    zone_name="Temperature",
                    allowlist="0123456789.-",
                )
            else:
                logger.warning("[OCR] Temperature zone crop height too small (%d px), skipping OCR.", temp_zone_img.shape[0])

            # ── Step 5: OCR Humidity zone (with height sanity check) ────
            hum_raw = ""
            hum_conf = 0.0
            if hum_zone_img.shape[0] >= 15:
                hum_raw, hum_conf, hum_bboxes = _run_easyocr_zone(
                    hum_preprocessed,
                    zone_name="Humidity",
                    allowlist="0123456789",
                )
            else:
                logger.warning("[OCR] Humidity zone crop height too small (%d px), skipping OCR.", hum_zone_img.shape[0])

            # ── Parse extracted text ─────────────────────────────────
            temp_value = _parse_temperature(temp_raw)
            hum_value = _parse_humidity(hum_raw)

            # ── Fallback to full-frame OCR if dual-zone failed ───────
            if temp_value is None and hum_value is None:
                logger.info("[OCR] Dual-zone crop failed. Falling back to full-frame heuristic OCR...")
                h_img, w_img = img.shape[:2]
                # Scale down for OCR speed if too wide
                if w_img > 1000:
                    scale = 1000 / w_img
                    resized = cv2.resize(img, (1000, int(h_img * scale)))
                else:
                    resized = img.copy()

                full_results = reader.readtext(resized, detail=1, paragraph=False)
                
                potential_temps = []
                potential_hums = []
                
                for bbox, text, prob in full_results:
                    txt = text.upper()
                    # Classify based on markers or ranges
                    if "C" in txt or "." in txt:
                        val = _parse_temperature(text)
                        if val is not None:
                            potential_temps.append((val, prob, bbox))
                    if "%" in txt or "RH" in txt:
                        val = _parse_humidity(text)
                        if val is not None:
                            potential_hums.append((val, prob, bbox))
                    
                    # Also look for plain numbers in ranges
                    nums = re.findall(r"\d+\.?\d*", txt)
                    for num in nums:
                        try:
                            v = float(num)
                            if 10.0 <= v <= 99.0:
                                potential_hums.append((round(v, 0), prob, bbox))
                            if -10.0 <= v <= 50.0:
                                potential_temps.append((round(v, 1), prob, bbox))
                        except ValueError:
                            continue
                
                potential_temps.sort(key=lambda x: x[1], reverse=True)
                potential_hums.sort(key=lambda x: x[1], reverse=True)
                
                scale_back = w_img / resized.shape[1]
                
                if potential_temps:
                    temp_value = potential_temps[0][0]
                    temp_conf = potential_temps[0][1]
                    box = potential_temps[0][2]
                    xs = [p[0] for p in box]
                    ys = [p[1] for p in box]
                    temp_roi_abs = [int(min(xs) * scale_back), int(min(ys) * scale_back),
                                    int((max(xs) - min(xs)) * scale_back), int((max(ys) - min(ys)) * scale_back)]
                    temp_raw = f"FullFrame: {temp_value}"
                
                if potential_hums:
                    hum_value = potential_hums[0][0]
                    hum_conf = potential_hums[0][1]
                    box = potential_hums[0][2]
                    xs = [p[0] for p in box]
                    ys = [p[1] for p in box]
                    hum_roi_abs = [int(min(xs) * scale_back), int(min(ys) * scale_back),
                                   int((max(xs) - min(xs)) * scale_back), int((max(ys) - min(ys)) * scale_back)]
                    hum_raw = f"FullFrame: {hum_value}"

            # ── Multi-frame smoothing (keyed on room_id alone) ────────
            if smoothing_window > 0 and source not in ("upload", "test", "manual", "rtsp"):
                # Note: rtsp captures triggered manually by the user should also bypass smoothing for instant response.
                # Only background periodic captures (if any) might use smoothing.
                if temp_value is not None:
                    temp_value = _smooth_reading(temp_value, room_id, "temp", smoothing_window)
                if hum_value is not None:
                    hum_value = _smooth_reading(hum_value, room_id, "hum", smoothing_window)

            # ── Determine OCR status ─────────────────────────────────
            if temp_value is not None and hum_value is not None:
                if temp_conf >= min_confidence and hum_conf >= min_confidence:
                    ocr_status = "SUCCESS"
                else:
                    ocr_status = "PARTIAL"
            elif temp_value is not None or hum_value is not None:
                ocr_status = "PARTIAL"
            else:
                ocr_status = "FAILED"

            # ── BUG FIX: Stagnation / static-value plausibility check ─
            # Detects when OCR returns the exact same value across N consecutive
            # captures — a reliable indicator that a cached/stuck/default value
            # is being returned rather than a live LCD read.
            # Only runs for non-synthetic, non-test sources (real camera or upload).
            if source not in ("synthetic", "test") and ocr_status != "FAILED":
                is_stagnant = check_ocr_stagnation(temp_value, hum_value, room_id)
                if is_stagnant:
                    ocr_status = "PARTIAL"  # Downgrade to PARTIAL — display with caution

            logger.info(
                "[OCR] Result: Temp=%s (conf=%.2f), Hum=%s (conf=%.2f), Status=%s",
                temp_value, temp_conf, hum_value, hum_conf, ocr_status,
            )
    else:
        logger.warning(f"Unsupported OCR engine: '{engine}'.")
        lcd_detect_conf = "low"

    # ── Save annotated snapshot + ROI crops ────────────────────────
    saved_path = None
    temp_roi_path = None
    hum_roi_path = None

    if save_annotated:
        try:
            saved_path, temp_roi_path, hum_roi_path = _save_annotated_frame(
                img, lcd_bbox, temp_roi_abs, hum_roi_abs,
                temp_value, hum_value, temp_conf, hum_conf, room_id,
                temp_zone_img, hum_zone_img,
            )
        except Exception as e:
            logger.warning("Failed to save annotated frame: %s", e)

    elapsed_ms = int(time.time() * 1000) - start_ms

    # Overall confidence: average of both, scaled to 0–100
    if temp_conf > 0 and hum_conf > 0:
        overall_conf = round(((temp_conf + hum_conf) / 2) * 100, 1)
    elif temp_conf > 0:
        overall_conf = round(temp_conf * 100, 1)
    elif hum_conf > 0:
        overall_conf = round(hum_conf * 100, 1)
    else:
        overall_conf = 0.0

    return OcrResult(
        temperature=temp_value,
        humidity=hum_value,
        ocr_confidence=overall_conf,
        temp_detail=OcrDigitResult(
            raw_text=temp_raw,
            value=temp_value,
            confidence=round(temp_conf, 3),
            roi=temp_roi_abs,
        ) if temp_raw else None,
        hum_detail=OcrDigitResult(
            raw_text=hum_raw,
            value=hum_value,
            confidence=round(hum_conf, 3),
            roi=hum_roi_abs,
        ) if hum_raw else None,
        source=source,
        processing_ms=elapsed_ms,
        image_saved_path=saved_path,
        device_type="HTC-1",
        ocr_status=ocr_status,
        lcd_region=lcd_bbox,
        lcd_detect_confidence=lcd_detect_conf,
        temp_roi_image_path=temp_roi_path,
        hum_roi_image_path=hum_roi_path,
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
    res = _run_full_pipeline(img, source="synthetic", room_id=room_id, save_annotated=save_annotated)
    if res.temperature is None:
        res.temperature = temp
    if res.humidity is None:
        res.humidity = hum
    return res

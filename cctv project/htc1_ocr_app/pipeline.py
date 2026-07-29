"""
HTC-1 LCD Digital Display OCR Reader — Main Processing Pipeline.

Orchestrates:
  1. Input Stream Acquisition (RTSP / Video File / Synthetic Generator)
  2. Dynamic ROI Tracking (Template / ArUco)
  3. Preprocessing (Perspective Warp, Super-Res, CLAHE, Binarization)
  4. 7-Segment OCR Extraction
  5. Rolling Temporal Filtering
  6. Video Stream Visual Overlay Rendering
  7. Multi-Sink Logging (CSV, SQLite/Postgres DB, HTTP Webhook, MQTT)
"""

import cv2
import time
import yaml
import logging
import numpy as np
import math
import random
from typing import Tuple, Optional, Dict

from htc1_ocr_app.preprocessor import ImagePreprocessor
from htc1_ocr_app.tracker import ROITracker
from htc1_ocr_app.segment_decoder import (
    SevenSegmentDecoder,
    EasyOCRBackend,
    TesseractBackend,
    parse_temperature_val,
    parse_humidity_val,
)
from htc1_ocr_app.smoother import TemporalFilter
from htc1_ocr_app.logger import ReadingLogger

logger = logging.getLogger(__name__)


def draw_7segment_digit(img: np.ndarray, x: int, y: int, w: int, h: int, digit_char: str, color=(230, 250, 220), thickness=4):
    SEG_PATTERNS = {
        '0': (1, 1, 1, 1, 1, 1, 0),
        '1': (0, 1, 1, 0, 0, 0, 0),
        '2': (1, 1, 0, 1, 1, 0, 1),
        '3': (1, 1, 1, 1, 0, 0, 1),
        '4': (0, 1, 1, 0, 0, 1, 1),
        '5': (1, 0, 1, 1, 0, 1, 1),
        '6': (1, 0, 1, 1, 1, 1, 1),
        '7': (1, 1, 1, 0, 0, 0, 0),
        '8': (1, 1, 1, 1, 1, 1, 1),
        '9': (1, 1, 1, 1, 0, 1, 1),
    }
    pattern = SEG_PATTERNS.get(digit_char, (0, 0, 0, 0, 0, 0, 0))
    a, b, c, d, e, f, g = pattern

    dw = thickness // 2
    mid_y = y + h // 2

    # A: Top
    if a: cv2.line(img, (x + dw, y), (x + w - dw, y), color, thickness)
    # B: Top-Right
    if b: cv2.line(img, (x + w, y + dw), (x + w, mid_y - dw), color, thickness)
    # C: Bottom-Right
    if c: cv2.line(img, (x + w, mid_y + dw), (x + w, y + h - dw), color, thickness)
    # D: Bottom
    if d: cv2.line(img, (x + dw, y + h), (x + w - dw, y + h), color, thickness)
    # E: Bottom-Left
    if e: cv2.line(img, (x, mid_y + dw), (x, y + h - dw), color, thickness)
    # F: Top-Left
    if f: cv2.line(img, (x, y + dw), (x, mid_y - dw), color, thickness)
    # G: Middle
    if g: cv2.line(img, (x + dw, mid_y), (x + w - dw, mid_y), color, thickness)


def create_synthetic_frame(step_index: int = 0) -> Tuple[np.ndarray, float, float]:
    """Generates a realistic synthetic test video frame with an embedded HTC-1 LCD meter."""
    W, H = 640, 480
    frame = np.zeros((H, W, 3), dtype=np.uint8)

    # Background CCTV room scene simulation
    frame[:, :] = (35, 30, 25)
    cv2.putText(frame, "CCTV CAM 01 -- DEMO STREAM", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    # Calculate smooth test temperature & humidity values
    t_val = round(24.5 + 2.0 * math.sin(step_index * 0.1), 1)
    h_val = round(52.0 + 5.0 * math.cos(step_index * 0.1), 1)

    # Meter LCD panel position in frame (matches default ROI [180, 140, 280, 200])
    x, y, w, h = 180, 140, 280, 200

    # Draw meter body & LCD screen background
    cv2.rectangle(frame, (x - 10, y - 10), (x + w + 10, y + h + 10), (60, 60, 60), -1)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (45, 55, 40), -1)

    # Draw Upper LCD: Temperature digits (e.g. "24.5")
    t_str = f"{t_val:04.1f}" # e.g. "24.5"
    digits_t = t_str.replace('.', '')
    start_x = x + 30
    digit_w, digit_h = 35, 60
    gap = 15

    for i, char in enumerate(digits_t):
        dx = start_x + i * (digit_w + gap)
        draw_7segment_digit(frame, dx, y + 20, digit_w, digit_h, char)

    # Decimal point
    cv2.circle(frame, (start_x + 2 * (digit_w + gap) - 8, y + 20 + digit_h), 3, (230, 250, 220), -1)

    # Draw Lower LCD: Humidity digits (e.g. "52")
    h_str = f"{int(h_val):02d}"
    start_x_h = x + 120
    for i, char in enumerate(h_str):
        dx = start_x_h + i * (digit_w + gap)
        draw_7segment_digit(frame, dx, y + 110, digit_w, digit_h, char)

    return frame, t_val, h_val


class LCDOCRProcessor:
    """Main execution pipeline processor."""

    def __init__(self, config_path: str):
        self.config_path = config_path
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.preprocessor = ImagePreprocessor(self.config.get("preprocessing", {}))
        self.tracker = ROITracker(self.config)
        self.smoother = TemporalFilter(self.config)
        self.logger_sink = ReadingLogger(self.config)

        # Select swappable OCR backend engine
        engine_type = self.config.get("ocr", {}).get("engine", "7segment").lower()
        if engine_type == "easyocr":
            self.ocr_engine = EasyOCRBackend()
        elif engine_type == "tesseract":
            self.ocr_engine = TesseractBackend()
        else:
            self.ocr_engine = SevenSegmentDecoder()

        self.roi = self.config.get("roi", {}).get("bounding_box", [180, 140, 280, 200])
        self.perspective_corners = self.config.get("roi", {}).get("perspective_corners", [])

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, Optional[float], Optional[float], float]:
        """
        Executes single-frame pipeline steps:
          Track ROI -> Preprocess -> Decode OCR -> Smooth -> Render Overlay.
        Returns (annotated_frame, filtered_temp, filtered_hum, confidence).
        """
        t0 = time.perf_counter()

        # 1. ROI Tracking
        current_roi, tracking_conf = self.tracker.track(frame)

        # Initialize template on first pass if tracking enabled
        if self.tracker.template is None and self.tracker.enabled:
            self.tracker.initialize_template(frame, current_roi)

        # 2. Image Preprocessing
        scaled, enhanced, binary = self.preprocessor.process(frame, current_roi, self.perspective_corners)

        # 3. Dual-Zone Splitting & OCR Extraction
        h_b, w_b = binary.shape[:2]
        temp_pct = self.config.get("ocr", {}).get("temp_zone_pct", [5, 55])
        hum_pct = self.config.get("ocr", {}).get("hum_zone_pct", [45, 95])

        temp_y1, temp_y2 = int(h_b * temp_pct[0] / 100), int(h_b * temp_pct[1] / 100)
        hum_y1, hum_y2 = int(h_b * hum_pct[0] / 100), int(h_b * hum_pct[1] / 100)

        temp_zone = binary[temp_y1:temp_y2, :]
        hum_zone = binary[hum_y1:hum_y2, int(w_b * 0.30):]

        raw_temp_str, conf_temp = self.ocr_engine.recognize_zone(temp_zone)
        raw_hum_str, conf_hum = self.ocr_engine.recognize_zone(hum_zone)

        raw_temp_val = parse_temperature_val(raw_temp_str)
        raw_hum_val = parse_humidity_val(raw_hum_str)

        # 4. Rolling Temporal Filtering
        filt_temp, filt_hum = self.smoother.filter(raw_temp_val, raw_hum_val)
        avg_conf = (conf_temp + conf_hum) / 2.0 if (conf_temp and conf_hum) else max(conf_temp, conf_hum, 0.5)

        # 5. Log Readings
        if filt_temp is not None or filt_hum is not None:
            self.logger_sink.log(filt_temp, filt_hum, avg_conf, status="normal")

        # 6. Render Video Overlay
        annotated = frame.copy()
        rx, ry, rw, rh = current_roi
        cv2.rectangle(annotated, (rx, ry), (rx + rw, ry + rh), (0, 255, 160), 2)

        # Draw HUD label box
        cv2.rectangle(annotated, (rx, ry - 35), (rx + rw, ry), (15, 23, 42), -1)
        temp_disp = f"{filt_temp:.1f}°C" if filt_temp is not None else "--.-°C"
        hum_disp = f"{int(filt_hum)}%RH" if filt_hum is not None else "--%RH"
        hud_text = f"TEMP: {temp_disp}  HUM: {hum_disp}"
        cv2.putText(annotated, hud_text, (rx + 8, ry - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

        # Processing latency
        proc_ms = (time.perf_counter() - t0) * 1000.0
        cv2.putText(annotated, f"FPS: {1000.0/max(1.0, proc_ms):.1f} | OCR Latency: {proc_ms:.1f}ms", (20, frame.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (56, 189, 248), 1, cv2.LINE_AA)

        return annotated, filt_temp, filt_hum, avg_conf

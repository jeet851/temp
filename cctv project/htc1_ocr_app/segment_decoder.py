"""
HTC-1 LCD Digital Display OCR Reader — 7-Segment OCR Engine & Decoder.

Includes:
  1. Custom 7-Segment Digit State Decoder (inspects 7 segment regions per digit box)
  2. Swappable OCR Engine Wrappers (SevenSegmentDecoder, EasyOCRBackend, TesseractBackend)
"""

import cv2
import numpy as np
import logging
import re
from dataclasses import dataclass
from typing import Tuple, List, Optional, Dict

logger = logging.getLogger(__name__)


@dataclass
class DigitResult:
    digit: str
    confidence: float
    bbox: Tuple[int, int, int, int]


@dataclass
class OCRParsedReading:
    raw_text: str
    temperature: Optional[float]
    humidity: Optional[float]
    confidence: float
    processing_ms: float
    engine_name: str


# 7-Segment State Map: (A, B, C, D, E, F, G)
# A: top, B: top-right, C: bottom-right, D: bottom, E: bottom-left, F: top-left, G: middle
SEGMENT_MAP: Dict[Tuple[int, int, int, int, int, int, int], str] = {
    (1, 1, 1, 1, 1, 1, 0): "0",
    (0, 1, 1, 0, 0, 0, 0): "1",
    (1, 1, 0, 1, 1, 0, 1): "2",
    (1, 1, 1, 1, 0, 0, 1): "3",
    (0, 1, 1, 0, 0, 1, 1): "4",
    (1, 0, 1, 1, 0, 1, 1): "5",
    (1, 0, 1, 1, 1, 1, 1): "6",
    (1, 1, 1, 0, 0, 0, 0): "7",
    (1, 1, 1, 1, 1, 1, 1): "8",
    (1, 1, 1, 1, 0, 1, 1): "9",
}


class SevenSegmentDecoder:
    """Detects digit bounding boxes and decodes 7-segment state maps."""

    def __init__(self, segment_threshold: float = 0.35):
        self.segment_threshold = segment_threshold

    def decode_digit_crop(self, digit_binary: np.ndarray) -> Tuple[Optional[str], float]:
        """
        Evaluates the 7 segment regions (A..G) in a binary single-digit ROI crop.
        Returns (digit_char, confidence).
        """
        h, w = digit_binary.shape[:2]
        if h < 8 or w < 4:
            return None, 0.0

        # Define 7 relative segment sampling regions (x, y, w, h)
        dw = int(w * 0.25)
        dh = int(h * 0.15)
        mid_y = int(h * 0.5)

        segments = {
            'A': (dw, 0, w - 2 * dw, dh),                         # Top
            'B': (w - dw, dh, dw, mid_y - dh),                     # Top-Right
            'C': (w - dw, mid_y, dw, h - mid_y - dh),              # Bottom-Right
            'D': (dw, h - dh, w - 2 * dw, dh),                     # Bottom
            'E': (0, mid_y, dw, h - mid_y - dh),                   # Bottom-Left
            'F': (0, dh, dw, mid_y - dh),                          # Top-Left
            'G': (dw, mid_y - dh // 2, w - 2 * dw, dh)             # Middle
        }

        states = []
        seg_order = ['A', 'B', 'C', 'D', 'E', 'F', 'G']

        for seg in seg_order:
            sx, sy, sw, sh = segments[seg]
            sx, sy = max(0, sx), max(0, sy)
            sw, sh = min(w - sx, sw), min(h - sy, sh)
            
            patch = digit_binary[sy:sy + sh, sx:sx + sw]
            if patch.size == 0:
                states.append(0)
                continue

            on_ratio = np.mean(patch > 0)
            states.append(1 if on_ratio >= self.segment_threshold else 0)

        t_state = tuple(states)
        if t_state in SEGMENT_MAP:
            return SEGMENT_MAP[t_state], 0.95

        # Fuzzy distance match to nearest valid 7-segment pattern
        best_match = None
        min_dist = 999
        for pattern, char in SEGMENT_MAP.items():
            dist = sum(abs(a - b) for a, b in zip(t_state, pattern))
            if dist < min_dist:
                min_dist = dist
                best_match = char

        if min_dist <= 2 and best_match is not None:
            confidence = max(0.40, 0.90 - 0.20 * min_dist)
            return best_match, confidence

        return None, 0.0

    def extract_digits(self, binary_zone: np.ndarray) -> List[DigitResult]:
        """Finds candidate digit contours and decodes each position."""
        contours, _ = cv2.findContours(binary_zone, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        h_zone, w_zone = binary_zone.shape[:2]

        digit_boxes = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            aspect = h / float(max(1, w))
            area_ratio = (w * h) / float(w_zone * h_zone)

            # Filter valid digit proportions
            if 1.1 <= aspect <= 4.5 and 0.02 <= area_ratio <= 0.40 and h >= h_zone * 0.35:
                digit_boxes.append((x, y, w, h))

        # Sort digits left to right
        digit_boxes.sort(key=lambda b: b[0])

        results = []
        for (x, y, w, h) in digit_boxes:
            crop = binary_zone[y:y + h, x:x + w]
            char, conf = self.decode_digit_crop(crop)
            if char is not None:
                results.append(DigitResult(digit=char, confidence=conf, bbox=(x, y, w, h)))

        return results

    def recognize_zone(self, binary_zone: np.ndarray) -> Tuple[str, float]:
        """Recognizes digits in a zone and returns (text_string, average_confidence)."""
        digits = self.extract_digits(binary_zone)
        if not digits:
            return "", 0.0

        raw_str = "".join([d.digit for d in digits])
        avg_conf = sum([d.confidence for d in digits]) / float(len(digits))
        return raw_str, avg_conf


class EasyOCRBackend:
    """Wrapper for EasyOCR backend."""

    def __init__(self, min_confidence: float = 0.5):
        self.min_confidence = min_confidence
        self._reader = None

    def _init_reader(self):
        if self._reader is None:
            import easyocr
            self._reader = easyocr.Reader(['en'], gpu=False, verbose=False)

    def recognize_zone(self, image: np.ndarray) -> Tuple[str, float]:
        try:
            self._init_reader()
            results = self._reader.readtext(image, allowlist="0123456789.-", detail=1)
            if not results:
                return "", 0.0
            texts = [r[1] for r in results]
            confs = [r[2] for r in results]
            return " ".join(texts), sum(confs) / len(confs)
        except Exception as e:
            logger.debug(f"EasyOCR error ({e}).")
            return "", 0.0


class TesseractBackend:
    """Wrapper for Tesseract OCR backend."""

    def __init__(self):
        pass

    def recognize_zone(self, image: np.ndarray) -> Tuple[str, float]:
        try:
            import pytesseract
            config = "--psm 7 -c tessedit_char_whitelist=0123456789.-"
            text = pytesseract.image_to_string(image, config=config).strip()
            return text, 0.80 if text else 0.0
        except Exception as e:
            logger.debug(f"Tesseract error ({e}).")
            return "", 0.0


def parse_temperature_val(raw_text: str) -> Optional[float]:
    """Parses temperature value (°C) with range check (-20°C to 80°C)."""
    cleaned = re.sub(r'[^\d.-]', '', raw_text)
    if not cleaned:
        return None
    try:
        val = float(cleaned)
        if -20.0 <= val <= 80.0:
            return round(val, 1)
        if val > 100 and "." not in cleaned and len(cleaned) == 3:
            val = val / 10.0
            if -20.0 <= val <= 80.0:
                return round(val, 1)
    except ValueError:
        pass
    return None


def parse_humidity_val(raw_text: str) -> Optional[float]:
    """Parses humidity value (%RH) with range check (0% to 100%)."""
    cleaned = re.sub(r'[^\d.]', '', raw_text)
    if not cleaned:
        return None
    try:
        val = float(cleaned)
        if 0.0 <= val <= 100.0:
            return round(val, 1)
    except ValueError:
        pass
    return None

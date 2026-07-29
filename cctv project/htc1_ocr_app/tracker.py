"""
HTC-1 LCD Digital Display OCR Reader — ROI Tracking Module.

Provides:
  - Template matching re-locking (cv2.matchTemplate) for camera vibration
  - ArUco marker detection & alignment (cv2.aruco)
"""

import cv2
import numpy as np
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class ROITracker:
    """Tracks ROI displacement using template matching or ArUco markers."""

    def __init__(self, config: dict):
        self.config = config.get("tracking", {})
        self.enabled = self.config.get("enabled", True)
        self.method = self.config.get("method", "template").lower()
        self.match_threshold = self.config.get("match_threshold", 0.65)
        self.aruco_marker_id = self.config.get("aruco_marker_id", 0)

        self.template: Optional[np.ndarray] = None
        self.initial_roi: Optional[List[int]] = None
        self.last_known_roi: Optional[List[int]] = None

    def initialize_template(self, frame: np.ndarray, roi: List[int]):
        """Saves template patch from initial reference frame."""
        self.initial_roi = list(roi)
        self.last_known_roi = list(roi)
        x, y, w, h = roi
        h_f, w_f = frame.shape[:2]
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(w_f, x + w), min(h_f, y + h)
        
        patch = frame[y1:y2, x1:x2]
        if patch.size > 0:
            self.template = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY) if len(patch.shape) == 3 else patch.copy()
            logger.info(f"ROI Template initialized ({w}x{h} px).")

    def track(self, frame: np.ndarray) -> Tuple[List[int], float]:
        """
        Calculates updated ROI coordinates for current frame.
        Returns (updated_roi_[x, y, w, h], confidence_score).
        """
        if not self.enabled or self.initial_roi is None:
            return self.initial_roi or [0, 0, 100, 100], 1.0

        if self.method == "aruco":
            return self._track_aruco(frame)

        return self._track_template(frame)

    def _track_template(self, frame: np.ndarray) -> Tuple[List[int], float]:
        """Tracks ROI displacement via cv2.matchTemplate around last known ROI location."""
        if self.template is None:
            return self.initial_roi, 1.0

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        h_f, w_f = gray.shape[:2]
        
        # Search window around last known ROI (expanded by 40px in each direction)
        ix, iy, iw, ih = self.last_known_roi
        margin = 40
        search_x1 = max(0, ix - margin)
        search_y1 = max(0, iy - margin)
        search_x2 = min(w_f, ix + iw + margin)
        search_y2 = min(h_f, iy + ih + margin)

        search_area = gray[search_y1:search_y2, search_x1:search_x2]
        th, tw = self.template.shape[:2]

        if search_area.shape[0] < th or search_area.shape[1] < tw:
            return self.last_known_roi, 0.0

        res = cv2.matchTemplate(search_area, self.template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val >= self.match_threshold:
            new_x = search_x1 + max_loc[0]
            new_y = search_y1 + max_loc[1]
            updated_roi = [int(new_x), int(new_y), int(iw), int(ih)]
            self.last_known_roi = updated_roi
            return updated_roi, float(max_val)

        logger.debug(f"Template match below threshold ({max_val:.2f} < {self.match_threshold}). Returning last known ROI.")
        return self.last_known_roi, float(max_val)

    def _track_aruco(self, frame: np.ndarray) -> Tuple[List[int], float]:
        """Tracks ROI displacement via ArUco marker detection."""
        try:
            if hasattr(cv2, "aruco"):
                dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
                parameters = cv2.aruco.DetectorParameters()
                detector = cv2.aruco.ArucoDetector(dictionary, parameters)
                corners, ids, _ = detector.detectMarkers(frame)

                if ids is not None and self.aruco_marker_id in ids.flatten():
                    idx = np.where(ids.flatten() == self.aruco_marker_id)[0][0]
                    m_corners = corners[idx][0] # 4 corners of marker
                    center_x = int(np.mean(m_corners[:, 0]))
                    center_y = int(np.mean(m_corners[:, 1]))

                    # Offset ROI from marker center
                    iw, ih = self.initial_roi[2], self.initial_roi[3]
                    updated_roi = [center_x - iw // 2, center_y - ih // 2, iw, ih]
                    self.last_known_roi = updated_roi
                    return updated_roi, 0.95
        except Exception as e:
            logger.debug(f"ArUco tracking error ({e}).")

        return self.last_known_roi or self.initial_roi, 0.0

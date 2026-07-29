"""
HTC-1 LCD Digital Display OCR Reader — Temporal Smoothing Module.

Applies:
  - Rolling buffer of size N
  - Mode / Median / EMA filtering
  - Outlier rejection (rejects values > 3σ from rolling mean)
"""

import numpy as np
import logging
from collections import deque, Counter
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)


class TemporalFilter:
    """Sliding window temporal filter for suppressing transient OCR misreads."""

    def __init__(self, config: dict):
        tf_cfg = config.get("temporal_filter", {})
        self.buffer_size = tf_cfg.get("buffer_size", 7)
        self.filter_method = tf_cfg.get("filter_method", "mode").lower()
        self.max_std_threshold = tf_cfg.get("max_std_threshold", 3.0)

        self._temp_history = deque(maxlen=self.buffer_size)
        self._hum_history = deque(maxlen=self.buffer_size)

    def filter_value(self, val: Optional[float], history: deque) -> Optional[float]:
        """Filters a single metric value using history deque."""
        if val is None:
            return self._compute_buffer_output(history)

        # Outlier rejection check
        if len(history) >= 3:
            mean = np.mean(history)
            std = max(0.1, np.std(history))
            if abs(val - mean) > self.max_std_threshold * std:
                logger.debug(f"[Filter] Outlier rejected: val={val} (mean={mean:.1f}, std={std:.1f})")
                return self._compute_buffer_output(history)

        history.append(val)
        return self._compute_buffer_output(history)

    def _compute_buffer_output(self, history: deque) -> Optional[float]:
        """Computes mode, median, or EMA of buffer values."""
        if not history:
            return None

        arr = list(history)

        if self.filter_method == "median":
            return float(round(np.median(arr), 1))

        if self.filter_method == "ema":
            alpha = 0.4
            ema = arr[0]
            for v in arr[1:]:
                ema = alpha * v + (1 - alpha) * ema
            return float(round(ema, 1))

        # Default: "mode" (most frequent reading)
        counts = Counter(arr)
        most_common = counts.most_common(1)[0][0]
        return float(round(most_common, 1))

    def filter(self, temp: Optional[float], hum: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
        """Applies temporal filtering to temperature and humidity readings."""
        filtered_temp = self.filter_value(temp, self._temp_history)
        filtered_hum = self.filter_value(hum, self._hum_history)
        return filtered_temp, filtered_hum

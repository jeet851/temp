"""
Unit tests for SevenSegmentDecoder and Preprocessor.
"""

import unittest
import numpy as np
import cv2

from htc1_ocr_app.segment_decoder import (
    SevenSegmentDecoder,
    SEGMENT_MAP,
    parse_temperature_val,
    parse_humidity_val,
)
from htc1_ocr_app.preprocessor import ImagePreprocessor
from htc1_ocr_app.smoother import TemporalFilter


class TestSevenSegmentDecoder(unittest.TestCase):

    def setUp(self):
        self.decoder = SevenSegmentDecoder()

    def test_segment_mapping_all_digits(self):
        """Verify that all standard 7-segment state combinations map to 0-9 digits."""
        for pattern, char in SEGMENT_MAP.items():
            self.assertIn(char, "0123456789")
            self.assertEqual(len(pattern), 7)

    def test_parse_temperature(self):
        """Test temperature parser with standard and edge-case strings."""
        self.assertEqual(parse_temperature_val("24.5°C"), 24.5)
        self.assertEqual(parse_temperature_val("19.0"), 19.0)
        self.assertEqual(parse_temperature_val("-5.2"), -5.2)
        self.assertEqual(parse_temperature_val("254"), 25.4) # missing dot handling
        self.assertIsNone(parse_temperature_val("150.0")) # out of range

    def test_parse_humidity(self):
        """Test humidity parser with valid and out of range values."""
        self.assertEqual(parse_humidity_val("52%RH"), 52.0)
        self.assertEqual(parse_humidity_val("65.0"), 65.0)
        self.assertIsNone(parse_humidity_val("120%")) # out of range

    def test_temporal_filter(self):
        """Test mode-based temporal filtering on sliding window."""
        config = {"temporal_filter": {"buffer_size": 5, "filter_method": "mode"}}
        filt = TemporalFilter(config)
        
        readings = [24.5, 24.5, 99.9, 24.5, 24.5] # 99.9 is transient outlier
        output = None
        for r in readings:
            output, _ = filt.filter(r, None)
            
        self.assertEqual(output, 24.5)


if __name__ == "__main__":
    unittest.main()

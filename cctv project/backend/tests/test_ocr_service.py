"""
VisionGuard — OCR Service Unit Tests (Phase 2).

Tests the OCR pipeline stages in isolation:
  - Synthetic LCD image generation
  - Image pre-processing (grayscale, CLAHE, threshold)
  - ROI cropping validity
  - Digit parsing (including LCD misread correction)
  - Full end-to-end pipeline via extract_from_synthetic()
  - Config get/update
"""

import pytest
import numpy as np


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

def _make_blank_bgr(w: int = 360, h: int = 270) -> np.ndarray:
    """Return a plain dark BGR image for crop/preprocess tests."""
    return np.zeros((h, w, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# 1. Synthetic image generation
# ---------------------------------------------------------------------------

class TestSyntheticImageGeneration:
    def test_returns_ndarray(self):
        from app.services.ocr_service import _generate_synthetic_lcd_image
        img = _generate_synthetic_lcd_image(temp=24.5, hum=58.2)
        assert isinstance(img, np.ndarray)

    def test_image_dimensions(self):
        from app.services.ocr_service import _generate_synthetic_lcd_image
        img = _generate_synthetic_lcd_image()
        assert img.shape == (270, 360, 3), f"Expected (270, 360, 3), got {img.shape}"

    def test_image_dtype(self):
        from app.services.ocr_service import _generate_synthetic_lcd_image
        img = _generate_synthetic_lcd_image()
        assert img.dtype == np.uint8

    def test_different_values_produce_different_images(self):
        from app.services.ocr_service import _generate_synthetic_lcd_image
        img1 = _generate_synthetic_lcd_image(temp=20.0, hum=40.0)
        img2 = _generate_synthetic_lcd_image(temp=35.0, hum=80.0)
        # Images with different values should differ (at least in the digit region)
        assert not np.array_equal(img1, img2)


# ---------------------------------------------------------------------------
# 2. Image pre-processing
# ---------------------------------------------------------------------------

class TestPreprocessing:
    def test_returns_binary_image(self):
        from app.services.ocr_service import _preprocess_for_ocr
        img = _make_blank_bgr(100, 50)
        result = _preprocess_for_ocr(img)
        assert result.ndim == 2, "Preprocessed image should be grayscale (2D)"

    def test_upscales_image(self):
        from app.services.ocr_service import _preprocess_for_ocr
        img = _make_blank_bgr(50, 30)
        result = _preprocess_for_ocr(img)
        # Should be 3× upscaled
        assert result.shape[0] == 30 * 3
        assert result.shape[1] == 50 * 3

    def test_output_is_binary(self):
        from app.services.ocr_service import _preprocess_for_ocr
        img = _make_blank_bgr(80, 40)
        result = _preprocess_for_ocr(img)
        unique_values = np.unique(result)
        # Binary image should only have 0 and/or 255
        assert all(v in (0, 255) for v in unique_values), f"Non-binary values found: {unique_values}"


# ---------------------------------------------------------------------------
# 3. ROI cropping
# ---------------------------------------------------------------------------

class TestRoiCrop:
    def test_crop_returns_correct_shape(self):
        from app.services.ocr_service import _crop_roi
        img = _make_blank_bgr(360, 270)
        crop = _crop_roi(img, (43, 58, 110, 48))
        assert crop.shape == (48, 110, 3)

    def test_crop_clamps_to_bounds(self):
        from app.services.ocr_service import _crop_roi
        img = _make_blank_bgr(100, 100)
        # ROI extends beyond image — should be clamped, not raise
        crop = _crop_roi(img, (80, 80, 100, 100))
        assert crop.shape[0] > 0
        assert crop.shape[1] > 0

    def test_full_image_crop(self):
        from app.services.ocr_service import _crop_roi
        img = _make_blank_bgr(200, 150)
        crop = _crop_roi(img, (0, 0, 200, 150))
        assert crop.shape == (150, 200, 3)


# ---------------------------------------------------------------------------
# 4. Digit parsing
# ---------------------------------------------------------------------------

class TestDigitParsing:
    def test_parse_normal_temp(self):
        from app.services.ocr_service import _parse_numeric_value
        assert _parse_numeric_value("24.5", -40, 80, "temp") == 24.5

    def test_parse_normal_humidity(self):
        from app.services.ocr_service import _parse_numeric_value
        assert _parse_numeric_value("58.2%", 0, 100, "hum") == 58.2

    def test_lcd_misread_O_to_0(self):
        from app.services.ocr_service import _parse_numeric_value
        # 'O' (capital letter O) should be read as '0'
        result = _parse_numeric_value("2O.5", -40, 80, "temp")
        assert result == 20.5

    def test_lcd_misread_l_to_1(self):
        from app.services.ocr_service import _parse_numeric_value
        result = _parse_numeric_value("l8.3", -40, 80, "temp")
        assert result == 18.3

    def test_lcd_misread_S_to_5(self):
        from app.services.ocr_service import _parse_numeric_value
        result = _parse_numeric_value("S8.7", 0, 100, "hum")
        assert result == 58.7

    def test_strips_degree_symbol(self):
        from app.services.ocr_service import _parse_numeric_value
        assert _parse_numeric_value("27.1°C", -40, 80, "temp") == 27.1

    def test_strips_percent_rh(self):
        from app.services.ocr_service import _parse_numeric_value
        assert _parse_numeric_value("65.0%RH", 0, 100, "hum") == 65.0

    def test_out_of_range_returns_none(self):
        from app.services.ocr_service import _parse_numeric_value
        # 150°C is out of range [-40, 80]
        assert _parse_numeric_value("150.0", -40, 80, "temp") is None

    def test_negative_out_of_range_returns_none(self):
        from app.services.ocr_service import _parse_numeric_value
        assert _parse_numeric_value("-99.9", -40, 80, "temp") is None

    def test_no_numeric_returns_none(self):
        from app.services.ocr_service import _parse_numeric_value
        assert _parse_numeric_value("ERR", -40, 80, "temp") is None

    def test_empty_string_returns_none(self):
        from app.services.ocr_service import _parse_numeric_value
        assert _parse_numeric_value("", -40, 80, "temp") is None

    def test_comma_decimal_separator(self):
        from app.services.ocr_service import _parse_numeric_value
        # European-style decimal comma
        result = _parse_numeric_value("24,5", -40, 80, "temp")
        assert result == 24.5


# ---------------------------------------------------------------------------
# 5. Config management
# ---------------------------------------------------------------------------

class TestOcrConfig:
    def test_get_config_returns_dict(self):
        from app.services.ocr_service import get_ocr_config
        cfg = get_ocr_config()
        assert isinstance(cfg, dict)
        assert "ocr_engine" in cfg
        assert "temp_roi" in cfg
        assert "hum_roi" in cfg

    def test_update_config_persists(self):
        from app.services.ocr_service import get_ocr_config, update_ocr_config, _runtime_config
        original = get_ocr_config()["ocr_confidence_threshold"]

        update_ocr_config({"ocr_confidence_threshold": 0.99})
        assert get_ocr_config()["ocr_confidence_threshold"] == 0.99

        # Restore
        update_ocr_config({"ocr_confidence_threshold": original})
        _runtime_config.pop("ocr_confidence_threshold", None)

    def test_update_roi(self):
        from app.services.ocr_service import get_ocr_config, update_ocr_config, _runtime_config
        update_ocr_config({"temp_roi": [10, 20, 100, 40]})
        assert get_ocr_config()["temp_roi"] == [10, 20, 100, 40]
        # Clean up
        _runtime_config.pop("temp_roi", None)


# ---------------------------------------------------------------------------
# 6. Full pipeline — synthetic end-to-end (requires easyocr installed)
# ---------------------------------------------------------------------------

class TestFullPipelineSynthetic:
    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("easyocr"),
        reason="easyocr not installed"
    )
    def test_extract_returns_ocr_result(self):
        from app.services.ocr_service import extract_from_synthetic
        from app.schemas.ocr import OcrResult
        result = extract_from_synthetic(temp=24.5, hum=58.2, save_annotated=False)
        assert isinstance(result, OcrResult)

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("easyocr"),
        reason="easyocr not installed"
    )
    def test_temperature_in_valid_range(self):
        from app.services.ocr_service import extract_from_synthetic
        result = extract_from_synthetic(temp=24.5, hum=58.2, save_annotated=False)
        assert -40.0 <= result.temperature <= 80.0

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("easyocr"),
        reason="easyocr not installed"
    )
    def test_humidity_in_valid_range(self):
        from app.services.ocr_service import extract_from_synthetic
        result = extract_from_synthetic(temp=24.5, hum=58.2, save_annotated=False)
        assert 0.0 <= result.humidity <= 100.0

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("easyocr"),
        reason="easyocr not installed"
    )
    def test_processing_time_recorded(self):
        from app.services.ocr_service import extract_from_synthetic
        result = extract_from_synthetic(save_annotated=False)
        assert result.processing_ms >= 0

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("easyocr"),
        reason="easyocr not installed"
    )
    def test_source_is_synthetic(self):
        from app.services.ocr_service import extract_from_synthetic
        result = extract_from_synthetic(save_annotated=False)
        assert result.source == "synthetic"

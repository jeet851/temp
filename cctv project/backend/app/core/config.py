"""
VisionGuard — Application Configuration.

Loads environment variables via pydantic-settings and exposes
a single `settings` instance used across the application.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "VisionGuard"
    app_version: str = "2.0.0"
    app_env: str = "development"
    debug: bool = True

    # --- Database ---
    database_url: str = "postgresql+asyncpg://vg_admin:visionguard2026@localhost:5432/visionguard"

    # --- JWT ---
    jwt_secret_key: str = "vg-dev-secret-key-change-in-production-2026"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # --- CORS ---
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # --- Media ---
    media_dir: str = "media"

    # --- Logging ---
    log_dir: str = "logs"
    log_level: str = "INFO"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000

    # -------------------------------------------------------
    # Phase 2: OCR Pipeline Settings
    # -------------------------------------------------------

    # OCR engine selection: "easyocr" | "tesseract"
    ocr_engine: str = "easyocr"

    # EasyOCR language list (comma-separated, e.g. "en" or "en,ch_sim")
    ocr_language: str = "en"

    # Whether to use CUDA GPU acceleration for EasyOCR
    ocr_gpu: bool = False

    # Minimum per-character confidence to accept an OCR reading (0.0–1.0)
    ocr_confidence_threshold: float = 0.55

    # How often the scheduler triggers an OCR capture (seconds)
    ocr_capture_interval: int = 300

    # Single LCD bounding box for HTC-1 meter — "x,y,width,height" in pixels
    ocr_lcd_roi: str = "130,130,100,90"

    # LCD ROI for temperature digits — "x,y,width,height" in pixels
    ocr_temp_roi: str = "130,130,100,42"

    # LCD ROI for humidity digits — "x,y,width,height" in pixels
    ocr_hum_roi: str = "178,175,52,42"

    # Dual-zone LCD detection settings
    # Temperature zone: top/bottom as % of detected LCD height (Upper band: 0% to 44%)
    ocr_temp_zone_pct: str = "0,44"
    # Humidity zone: top/bottom as % of detected LCD height (Lower band: 65% to 100%)
    ocr_hum_zone_pct: str = "65,100"
    # Multi-frame smoothing window size (0 to disable)
    ocr_smoothing_window: int = 5
    # LCD detection mode: "contour" (auto-detect) or "fixed" (use pixel ROI)
    ocr_lcd_detect_mode: str = "contour"

    @property
    def ocr_lcd_roi_tuple(self) -> tuple[int, int, int, int]:
        """Parse single LCD meter ROI string into (x, y, w, h) integers."""
        x, y, w, h = (int(v.strip()) for v in self.ocr_lcd_roi.split(","))
        return x, y, w, h

    @property
    def ocr_temp_roi_tuple(self) -> tuple[int, int, int, int]:
        """Parse temperature ROI string into (x, y, w, h) integers."""
        x, y, w, h = (int(v.strip()) for v in self.ocr_temp_roi.split(","))
        return x, y, w, h

    @property
    def ocr_hum_roi_tuple(self) -> tuple[int, int, int, int]:
        """Parse humidity ROI string into (x, y, w, h) integers."""
        x, y, w, h = (int(v.strip()) for v in self.ocr_hum_roi.split(","))
        return x, y, w, h

    @property
    def ocr_temp_zone_tuple(self) -> tuple[int, int]:
        """Parse temperature zone percentages into (top%, bottom%)."""
        t, b = (int(v.strip()) for v in self.ocr_temp_zone_pct.split(","))
        return t, b

    @property
    def ocr_hum_zone_tuple(self) -> tuple[int, int]:
        """Parse humidity zone percentages into (top%, bottom%)."""
        t, b = (int(v.strip()) for v in self.ocr_hum_zone_pct.split(","))
        return t, b

    @property
    def ocr_language_list(self) -> list[str]:
        """Parse comma-separated language codes into a list for EasyOCR."""
        return [lang.strip() for lang in self.ocr_language.split(",")]


settings = Settings()

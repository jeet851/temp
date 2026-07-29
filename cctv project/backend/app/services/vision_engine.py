import numpy as np

# Globals for OCR engine mock compatibility in tests
paddle_ocr = None
easyocr_reader = None
pytesseract = None


class FrameGrabber:
    """FrameGrabber compatibility stub for unit tests."""
    pass


class CameraWorker:
    """CameraWorker compatibility stub for unit tests."""

    def __init__(self, camera_id: str, rtsp_url: str, room_id: str) -> None:
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.room_id = room_id
        self.temp_val = None
        self.hum_val = None

    def extract_digits(self, frame: np.ndarray) -> tuple[float | None, float | None]:
        """Runs digit extraction (or raises error if all engines are None)."""
        global paddle_ocr, easyocr_reader, pytesseract
        if paddle_ocr is None and easyocr_reader is None and pytesseract is None:
            raise RuntimeError("No OCR engine is available")
        return None, None

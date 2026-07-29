"""
HTC-1 LCD Digital Display OCR Reader — Image Preprocessing Module.

Applies:
  1. Perspective transformation (four-point warp)
  2. Super-resolution upscaling (OpenCV DNN EDSR/ESPCN with Lanczos fallback)
  3. CLAHE adaptive contrast enhancement
  4. 7-segment binary thresholding and morphological segment reconnection
"""

import cv2
import numpy as np
import logging
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)


def four_point_transform(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """
    Applies a 4-point perspective transform to extract a bird's-eye rectangular image.
    pts: Array of 4 (x, y) coordinates ordered: top-left, top-right, bottom-right, bottom-left.
    """
    pts = np.array(pts, dtype="float32")
    (tl, tr, br, bl) = pts

    # Compute width of new image
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    # Compute height of new image
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[0] - bl[0]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]
    ], dtype="float32")

    M = cv2.getPerspectiveTransform(pts, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped


class ImagePreprocessor:
    """Modular image preprocessor supporting OpenCV DNN Super-Resolution and 7-segment binarization."""

    def __init__(self, config: dict):
        self.config = config
        self.scale_factor = config.get("scale_factor", 3)
        self.super_res_model_name = config.get("super_res_model", "espcn").lower()
        self.super_res_model_path = config.get("super_res_model_path", "")
        self.clahe_clip_limit = config.get("clahe_clip_limit", 3.0)
        grid_size = config.get("clahe_grid_size", [8, 8])
        self.clahe_grid_size = tuple(grid_size)
        self.binarization_method = config.get("binarization_method", "otsu").lower()
        self.adaptive_block_size = config.get("adaptive_block_size", 11)
        self.adaptive_c = config.get("adaptive_c", 2)
        self.morph_kernel_size = config.get("morph_kernel_size", 2)

        self._sr_dnn = None
        self._init_super_resolution()

    def _init_super_resolution(self):
        """Try initializing OpenCV DNN Super-Resolution model if path exists."""
        if hasattr(cv2, "dnn_superres") and self.super_res_model_path:
            try:
                sr = cv2.dnn_superres.DnnSuperResImpl_create()
                sr.readModel(self.super_res_model_path)
                sr.setModel(self.super_res_model_name, self.scale_factor)
                self._sr_dnn = sr
                logger.info(f"OpenCV DNN Super-Resolution ({self.super_res_model_name} x{self.scale_factor}) initialized.")
            except Exception as e:
                logger.warning(f"Failed to load DNN Super-Res model ({e}). Using Lanczos4 interpolation fallback.")
                self._sr_dnn = None

    def upscale(self, image: np.ndarray) -> np.ndarray:
        """Upscales ROI using DNN Super-Resolution or high-quality Lanczos4 interpolation."""
        if self._sr_dnn is not None:
            try:
                return self._sr_dnn.upsample(image)
            except Exception as e:
                logger.debug(f"DNN upsample error ({e}); falling back to Lanczos4.")
        
        # High quality interpolation fallback
        h, w = image.shape[:2]
        new_w = w * self.scale_factor
        new_h = h * self.scale_factor
        return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

    def enhance_contrast(self, gray: np.ndarray) -> np.ndarray:
        """Applies CLAHE contrast enhancement for uneven CCTV lighting."""
        clahe = cv2.createCLAHE(clipLimit=self.clahe_clip_limit, tileGridSize=self.clahe_grid_size)
        return clahe.apply(gray)

    def binarize_segment_display(self, enhanced_gray: np.ndarray) -> np.ndarray:
        """Binarizes 7-segment LCD digits and applies morphological closing to reconnect broken segment lines."""
        blurred = cv2.GaussianBlur(enhanced_gray, (3, 3), 0)

        if self.binarization_method == "adaptive_gaussian":
            binary = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, self.adaptive_block_size, self.adaptive_c
            )
        elif self.binarization_method == "simple":
            _, binary = cv2.threshold(blurred, 127, 255, cv2.THRESH_BINARY)
        else: # "otsu" default
            _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Invert if needed: ensure digits are foreground (white = 255) and background is dark (0)
        border = np.concatenate([binary[0, :], binary[-1, :], binary[:, 0], binary[:, -1]])
        if np.mean(border) > 127:
            binary = cv2.bitwise_not(binary)

        # Morphological closing to reconnect broken LCD segments
        if self.morph_kernel_size > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (self.morph_kernel_size, self.morph_kernel_size))
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        return binary

    def process(self, frame: np.ndarray, roi: List[int], perspective_corners: Optional[List[List[int]]] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Complete preprocessing pipeline:
        Extracts ROI/warps -> upscales -> enhances contrast -> binarizes.
        Returns (cropped_bgr, enhanced_grayscale, binarized_mask).
        """
        if perspective_corners and len(perspective_corners) == 4:
            cropped = four_point_transform(frame, np.array(perspective_corners))
        else:
            x, y, w, h = roi
            img_h, img_w = frame.shape[:2]
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(img_w, x + w), min(img_h, y + h)
            cropped = frame[y1:y2, x1:x2]

        if cropped.size == 0:
            raise ValueError("ROI crop resulted in empty image. Check ROI coordinates.")

        # 1. Upscale
        scaled = self.upscale(cropped)

        # 2. Grayscale
        gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY) if len(scaled.shape) == 3 else scaled.copy()

        # 3. CLAHE Contrast enhancement
        enhanced = self.enhance_contrast(gray)

        # 4. Binarization
        binary = self.binarize_segment_display(enhanced)

        return scaled, enhanced, binary

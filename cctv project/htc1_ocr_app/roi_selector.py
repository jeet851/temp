"""
HTC-1 LCD Digital Display OCR Reader — Interactive ROI Selector Tool.

Launch with:
  python -m htc1_ocr_app.roi_selector --config htc1_ocr_app/config.yaml --source media/test_stream.mp4

Features:
  - Drag to select fixed ROI bounding box
  - Press 's' to save ROI coordinates to config.yaml
  - Press 'q' or ESC to exit
"""

import cv2
import yaml
import argparse
import sys
import os

def load_first_frame(source_path: str):
    """Opens video stream or file and grabs the first frame."""
    if source_path == "webcam" or source_path.isdigit():
        idx = 0 if source_path == "webcam" else int(source_path)
        cap = cv2.VideoCapture(idx)
    else:
        cap = cv2.VideoCapture(source_path)

    if not cap.isOpened():
        raise RuntimeError(f"Could not open video source: {source_path}")

    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise RuntimeError("Failed to read first frame from source.")
    return frame


def run_roi_selector(config_path: str, source_override: str = None):
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    source = source_override or config.get("input", {}).get("source", "0")
    print(f"Loading frame from source: {source}...")

    try:
        frame = load_first_frame(source)
    except Exception as e:
        print(f"Error: {e}")
        return

    window_name = "HTC-1 LCD ROI Selector — Drag ROI & Press 'S' to Save, 'Q' to Quit"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    # Use OpenCV built-in ROI selector
    roi = cv2.selectROI(window_name, frame, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow(window_name)

    x, y, w, h = [int(v) for v in roi]

    if w > 0 and h > 0:
        print(f"\nSelected ROI: x={x}, y={y}, w={w}, h={h}")
        config["roi"]["bounding_box"] = [x, y, w, h]

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False)

        print(f"✓ Saved updated ROI to {config_path} successfully!")
    else:
        print("Selection cancelled.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Interactive ROI Selector for HTC-1 LCD Reader")
    parser.add_argument("--config", default="htc1_ocr_app/config.yaml", help="Path to YAML config file")
    parser.add_argument("--source", default=None, help="Override video stream source or file")
    args = parser.parse_args()

    run_roi_selector(args.config, args.source)

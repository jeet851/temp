"""
HTC-1 LCD Digital Display OCR Reader — Main CLI Entry Point.

Usage:
  # Synthetic Demo Mode (no camera required):
  python -m htc1_ocr_app.main --synthetic

  # Custom Video File / RTSP Stream Mode:
  python -m htc1_ocr_app.main --source rtsp://admin:admin@123@10.215.75.201/live

  # Interactive ROI Selector:
  python -m htc1_ocr_app.main --select-roi

  # Benchmark Engine Accuracy:
  python -m htc1_ocr_app.main --benchmark
"""

import cv2
import time
import argparse
import sys
import os

from htc1_ocr_app.pipeline import LCDOCRProcessor, create_synthetic_frame
from htc1_ocr_app.roi_selector import run_roi_selector
from htc1_ocr_app.benchmark import run_benchmark


def main():
    parser = argparse.ArgumentParser(description="HTC-1 LCD Digital Display OCR Reader Application")
    parser.add_argument("--config", default="htc1_ocr_app/config.yaml", help="Path to YAML configuration file")
    parser.add_argument("--source", default=None, help="Override video stream source (RTSP URL, video file, or 'webcam')")
    parser.add_argument("--synthetic", action="store_true", help="Run in synthetic demonstration mode")
    parser.add_argument("--select-roi", action="store_true", help="Launch interactive ROI selector GUI")
    parser.add_argument("--benchmark", action="store_true", help="Run accuracy benchmark utility")
    parser.add_argument("--no-display", action="store_true", help="Disable GUI video window output (headless mode)")
    args = parser.parse_args()

    if args.select_roi:
        run_roi_selector(args.config, args.source)
        return

    if args.benchmark:
        run_benchmark("htc1_ocr_app/test_dataset", args.config)
        return

    processor = LCDOCRProcessor(args.config)
    source = args.source or processor.config.get("input", {}).get("source", "0")
    use_synthetic = args.synthetic or (source == "synthetic")

    show_display = not args.no_display and processor.config.get("output", {}).get("show_overlay", True)

    print(f"\n=========================================================")
    print(f" HTC-1 LCD Digital Display OCR Reader Application")
    print(f" Mode: {'Synthetic Demo' if use_synthetic else 'Live Video Stream'}")
    print(f" Source: {source}")
    print(f" Config: {args.config}")
    print(f"=========================================================\n")

    step_idx = 0

    if use_synthetic:
        window_name = "HTC-1 LCD Reader — Synthetic Demo (Press 'Q' to Exit)"
        if show_display:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        while True:
            frame, gt_t, gt_h = create_synthetic_frame(step_idx)
            step_idx += 1

            annotated, temp, hum, conf = processor.process_frame(frame)

            if show_display:
                cv2.imshow(window_name, annotated)
                key = cv2.waitKey(60) & 0xFF
                if key in [ord('q'), ord('Q'), 27]:
                    break
            else:
                print(f"[{step_idx:04d}] Temp: {temp}°C | Hum: {hum}%RH (Conf: {conf:.2f})")
                time.sleep(0.1)

        if show_display:
            cv2.destroyAllWindows()

    else:
        # Live video stream or file input
        if source == "webcam" or source.isdigit():
            idx = 0 if source == "webcam" else int(source)
            cap = cv2.VideoCapture(idx)
        else:
            cap = cv2.VideoCapture(source)

        if not cap.isOpened():
            print(f"Error: Unable to open video source: {source}")
            sys.exit(1)

        window_name = f"HTC-1 LCD Reader — Stream ({source})"
        if show_display:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or frame is None:
                # Loop video file if reached end
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
                if not ret:
                    break

            step_idx += 1
            annotated, temp, hum, conf = processor.process_frame(frame)

            if show_display:
                cv2.imshow(window_name, annotated)
                key = cv2.waitKey(30) & 0xFF
                if key in [ord('q'), ord('Q'), 27]:
                    break
            else:
                if step_idx % 15 == 0:
                    print(f"[{step_idx:04d}] Temp: {temp}°C | Hum: {hum}%RH (Conf: {conf:.2f})")

        cap.release()
        if show_display:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

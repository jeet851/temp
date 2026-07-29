"""
HTC-1 LCD Digital Display OCR Reader — Benchmark Utility.

Evaluates OCR engine accuracy against a folder of manually-labelled ground-truth frames.

Dataset directory structure:
  dataset/
    sample_001.jpg
    sample_001.json   ({"temperature": 24.5, "humidity": 58.0})
    sample_002.jpg
    sample_002.json   ({"temperature": 19.0, "humidity": 51.0})

Run with:
  python -m htc1_ocr_app.benchmark --dataset path/to/dataset --config htc1_ocr_app/config.yaml
"""

import os
import cv2
import json
import time
import yaml
import argparse
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple

from htc1_ocr_app.preprocessor import ImagePreprocessor
from htc1_ocr_app.segment_decoder import SevenSegmentDecoder, EasyOCRBackend, parse_temperature_val, parse_humidity_val


def run_benchmark(dataset_dir: str, config_path: str):
    if not os.path.exists(config_path):
        print(f"Error: Config file not found at {config_path}")
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    preprocessor = ImagePreprocessor(config.get("preprocessing", {}))
    decoder = SevenSegmentDecoder()
    roi = config.get("roi", {}).get("bounding_box", [0, 0, 200, 200])

    dataset_path = Path(dataset_dir)
    image_files = list(dataset_path.glob("*.jpg")) + list(dataset_path.glob("*.png"))

    if not image_files:
        print(f"No sample images found in dataset directory: {dataset_dir}")
        print("Generating synthetic benchmark test set...")
        # Create temporary synthetic test frames for benchmarking
        os.makedirs(dataset_dir, exist_ok=True)
        from htc1_ocr_app.pipeline import create_synthetic_frame
        for i in range(5):
            synth_frame, gt_temp, gt_hum = create_synthetic_frame(i)
            img_p = dataset_path / f"synth_{i:03d}.jpg"
            json_p = dataset_path / f"synth_{i:03d}.json"
            cv2.imwrite(str(img_p), synth_frame)
            with open(json_p, 'w') as jf:
                json.dump({"temperature": gt_temp, "humidity": gt_hum}, jf)
        image_files = list(dataset_path.glob("*.jpg"))

    print(f"\n=========================================================")
    print(f" HTC-1 LCD OCR Reader Benchmark Utility")
    print(f" Dataset Path: {dataset_dir}")
    print(f" Samples Found: {len(image_files)}")
    print(f"=========================================================\n")

    total_samples = 0
    temp_exact_matches = 0
    hum_exact_matches = 0
    temp_errors = []
    hum_errors = []
    latencies_ms = []

    for img_path in image_files:
        json_path = img_path.with_suffix('.json')
        if not json_path.exists():
            continue

        with open(json_path, 'r', encoding='utf-8') as jf:
            gt_data = json.load(jf)

        gt_temp = gt_data.get("temperature")
        gt_hum = gt_data.get("humidity")

        frame = cv2.imread(str(img_path))
        if frame is None:
            continue

        t0 = time.perf_counter()

        # Run pipeline steps
        try:
            scaled, enhanced, binary = preprocessor.process(frame, roi)

            # Split upper / lower zones
            h, w = binary.shape[:2]
            temp_zone = binary[int(h * 0.05):int(h * 0.55), :]
            hum_zone = binary[int(h * 0.45):int(h * 0.95), int(w * 0.30):]

            raw_temp_text, _ = decoder.recognize_zone(temp_zone)
            raw_hum_text, _ = decoder.recognize_zone(hum_zone)

            pred_temp = parse_temperature_val(raw_temp_text)
            pred_hum = parse_humidity_val(raw_hum_text)
        except Exception as e:
            pred_temp = None
            pred_hum = None

        t_ms = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(t_ms)
        total_samples += 1

        # Evaluate Temperature
        if gt_temp is not None:
            if pred_temp is not None and abs(pred_temp - gt_temp) < 0.1:
                temp_exact_matches += 1
            if pred_temp is not None:
                temp_errors.append(abs(pred_temp - gt_temp))

        # Evaluate Humidity
        if gt_hum is not None:
            if pred_hum is not None and abs(pred_hum - gt_hum) < 0.1:
                hum_exact_matches += 1
            if pred_hum is not None:
                hum_errors.append(abs(pred_hum - gt_hum))

        print(f"Sample [{img_path.name}]: GT Temp={gt_temp}°C, Pred Temp={pred_temp}°C | GT Hum={gt_hum}%, Pred Hum={pred_hum}% ({t_ms:.1f} ms)")

    if total_samples == 0:
        print("No valid sample/json pairs evaluated.")
        return

    avg_latency = np.mean(latencies_ms)
    temp_acc = (temp_exact_matches / total_samples) * 100.0
    hum_acc = (hum_exact_matches / total_samples) * 100.0
    mean_temp_err = np.mean(temp_errors) if temp_errors else 0.0
    mean_hum_err = np.mean(hum_errors) if hum_errors else 0.0

    print(f"\n---------------------------------------------------------")
    print(f" BENCHMARK RESULTS SUMMARY")
    print(f"---------------------------------------------------------")
    print(f" Total Evaluated Samples  : {total_samples}")
    print(f" Temperature Accuracy     : {temp_acc:.1f}% (MAE: {mean_temp_err:.2f}°C)")
    print(f" Humidity Accuracy        : {hum_acc:.1f}% (MAE: {mean_hum_err:.2f}%RH)")
    print(f" Average Processing Time  : {avg_latency:.2f} ms/frame ({1000.0/max(0.1, avg_latency):.1f} FPS)")
    print(f"---------------------------------------------------------\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark Utility for HTC-1 LCD OCR Reader")
    parser.add_argument("--dataset", default="htc1_ocr_app/test_dataset", help="Directory containing sample images and JSON ground truth")
    parser.add_argument("--config", default="htc1_ocr_app/config.yaml", help="Path to config file")
    args = parser.parse_args()

    run_benchmark(args.dataset, args.config)

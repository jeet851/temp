"""
HTC-1 LCD Digital Display OCR Reader — Logging Module.

Handles:
  - CSV file logging
  - SQLite / PostgreSQL database persistence
  - HTTP webhook notification dispatch
  - MQTT broker publishing
"""

import os
import csv
import sqlite3
import json
import logging
from datetime import datetime, timezone
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)


class ReadingLogger:
    """Multi-sink logger for environmental readings."""

    def __init__(self, config: dict):
        out_cfg = config.get("output", {})
        self.log_to_csv = out_cfg.get("log_to_csv", True)
        self.csv_filepath = out_cfg.get("csv_filepath", "readings_log.csv")

        self.log_to_db = out_cfg.get("log_to_db", True)
        self.db_url = out_cfg.get("db_url", "sqlite:///lcd_readings.db")

        self.log_to_http = out_cfg.get("log_to_http", False)
        self.http_url = out_cfg.get("http_url", "http://localhost:8000/api/v1/telemetry")

        self.log_to_mqtt = out_cfg.get("log_to_mqtt", False)
        self.mqtt_broker = out_cfg.get("mqtt_broker", "localhost")
        self.mqtt_port = out_cfg.get("mqtt_port", 1883)
        self.mqtt_topic = out_cfg.get("mqtt_topic", "visionguard/sensors/htc1")

        self._init_csv()
        self._init_db()

    def _init_csv(self):
        """Initializes CSV file header if file does not exist."""
        if self.log_to_csv and not os.path.exists(self.csv_filepath):
            try:
                with open(self.csv_filepath, mode='w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Timestamp", "Temperature_C", "Humidity_RH", "Confidence", "Status"])
                logger.info(f"CSV log initialized at {self.csv_filepath}")
            except Exception as e:
                logger.error(f"Failed to initialize CSV log: {e}")

    def _init_db(self):
        """Initializes SQLite database table."""
        if self.log_to_db and "sqlite" in self.db_url:
            try:
                db_path = self.db_url.replace("sqlite:///", "")
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS lcd_readings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        temperature REAL,
                        humidity REAL,
                        confidence REAL,
                        status TEXT
                    )
                """)
                conn.commit()
                conn.close()
                logger.info(f"SQLite DB initialized at {db_path}")
            except Exception as e:
                logger.error(f"Failed to initialize SQLite DB: {e}")

    def log(self, temp: Optional[float], hum: Optional[float], confidence: float = 1.0, status: str = "normal"):
        """Logs a reading snapshot to all enabled destinations."""
        ts = datetime.now(timezone.utc).isoformat()

        # 1. CSV File
        if self.log_to_csv:
            try:
                with open(self.csv_filepath, mode='a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([ts, temp if temp is not None else "", hum if hum is not None else "", f"{confidence:.2f}", status])
            except Exception as e:
                logger.error(f"CSV write error: {e}")

        # 2. SQLite Database
        if self.log_to_db and "sqlite" in self.db_url:
            try:
                db_path = self.db_url.replace("sqlite:///", "")
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO lcd_readings (timestamp, temperature, humidity, confidence, status) VALUES (?, ?, ?, ?, ?)",
                    (ts, temp, hum, confidence, status)
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"SQLite log error: {e}")

        # 3. HTTP Webhook
        if self.log_to_http and self.http_url:
            try:
                payload = json.dumps({
                    "timestamp": ts,
                    "temperature": temp,
                    "humidity": hum,
                    "confidence": confidence,
                    "status": status
                }).encode('utf-8')
                req = urllib.request.Request(self.http_url, data=payload, headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    pass
            except Exception as e:
                logger.debug(f"HTTP webhook dispatch error: {e}")

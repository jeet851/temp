"""
VisionGuard — Utility Helpers.

Common utility functions for date formatting, ID generation,
and file path management.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings


def generate_id(prefix: str = "") -> str:
    """
    Generate a unique string ID with an optional prefix.

    Args:
        prefix: Short prefix like 'r', 'h', 'alt' for readability.

    Returns:
        String like 'r-a1b2c3d4' or just 'a1b2c3d4'.
    """
    short_uuid = uuid.uuid4().hex[:12]
    return f"{prefix}-{short_uuid}" if prefix else short_uuid


def utc_now() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def format_iso(dt: datetime) -> str:
    """Format a datetime object as an ISO 8601 string."""
    return dt.isoformat()


def ensure_media_dirs() -> None:
    """Create media storage directories if they don't exist."""
    base = Path(settings.media_dir)
    for subdir in ["environment", "alerts", "exports"]:
        (base / subdir).mkdir(parents=True, exist_ok=True)


def get_media_path(category: str, filename: str) -> str:
    """
    Build a relative media file path.

    Args:
        category: 'environment', 'alerts', or 'exports'.
        filename: The file name.

    Returns:
        Relative path like 'media/environment/snap_001.jpg'.
    """
    return f"{settings.media_dir}/{category}/{filename}"

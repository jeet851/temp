"""
VisionGuard — ORM Models Package.

Imports all models so that Alembic and the app factory
can discover them via a single import.
"""

from app.models.user import User
from app.models.room import Room
from app.models.camera import Camera
from app.models.environmental_reading import EnvironmentalReading
from app.models.environmental_history import EnvironmentalHistory
from app.models.alert import Alert
from app.models.system_config import SystemConfig
from app.models.audit_log import AuditLog

__all__ = [
    "User",
    "Room",
    "Camera",
    "EnvironmentalReading",
    "EnvironmentalHistory",
    "Alert",
    "SystemConfig",
    "AuditLog",
]

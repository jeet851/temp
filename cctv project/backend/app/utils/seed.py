"""
VisionGuard — Database Seed Script.

Populates the database with initial data:
- 1 admin user (sysadmin@visionguard.net)
- 1 room (room-001: Server Room Alpha)
- 1 camera (camera-001: Alpha CCTV-1)
- 1 system_config row (default thresholds)
- 24 hours of simulated environmental history

Run with: python -m app.utils.seed
"""

import asyncio
import math
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.database.session import async_session_factory, engine
from app.database.base import Base
from app.models import (
    User,
    Room,
    Camera,
    SystemConfig,
    EnvironmentalReading,
    EnvironmentalHistory,
)
from app.utils.helpers import generate_id


async def seed_database() -> None:
    """Insert initial seed data if tables are empty."""

    async with async_session_factory() as db:
        # --- Check if already seeded ---
        existing_user = await db.execute(select(User).limit(1))
        if existing_user.scalar_one_or_none():
            print("Database already seeded. Skipping.")
            return

        print("Seeding database...")

        # --- Admin User ---
        admin = User(
            full_name="System Administrator",
            username="sysadmin",
            email="sysadmin@visionguard.net",
            password_hash=hash_password("VisionGuard2026!"),
            role="admin",
            status="active",
        )
        db.add(admin)
        print("  -> Admin user created: sysadmin@visionguard.net")

        # --- Room ---
        room = Room(
            id="room-001",
            name="Server Room Alpha",
            location="Building A, Floor 2, Zone C",
            status="normal",
        )
        db.add(room)
        print("  -> Room created: room-001 (Server Room Alpha)")

        # --- Camera ---
        camera = Camera(
            id="camera-001",
            name="Alpha CCTV-1",
            room_id="room-001",
            rtsp_url="rtsp://admin:admin@123@10.215.75.201/live",
            status="online",
            fps=15.0,
            latency_ms=120,
            ocr_confidence=96.0,
        )
        db.add(camera)
        print("  -> Camera created: camera-001 (Alpha CCTV-1)")

        # --- System Config ---
        config = SystemConfig(
            temp_warning=28.0,
            temp_critical=32.0,
            hum_warning=65.0,
            hum_critical=75.0,
            capture_interval=300,
            ocr_polling_interval_seconds=300,
            allow_synthetic_fallback=True,
            retention_days=90,
            system_version="2.0.0",
        )
        db.add(config)
        print("  -> System config created with default thresholds (5-min capture interval)")

        await db.commit()
        print("Database seeding complete!")


async def main() -> None:
    """Create tables (if needed) and run seed."""
    # Import all models so metadata is populated
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await seed_database()


if __name__ == "__main__":
    asyncio.run(main())

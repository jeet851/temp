"""
VisionGuard — Data Reset / Purge Script.

Clears all stored environmental history, live telemetry readings, and alerts
from the database.

Run with: python -m app.utils.clear_data
"""

import asyncio
from sqlalchemy import delete
from app.database.session import async_session_factory
from app.models import EnvironmentalHistory, EnvironmentalReading, Alert, SystemConfig


async def clear_stored_data() -> None:
    """Purge all stored data from environmental_history, environmental_readings, and alerts tables."""
    async with async_session_factory() as db:
        print("Clearing all stored historical data...")

        # Delete history, readings, and alerts
        res_h = await db.execute(delete(EnvironmentalHistory))
        res_r = await db.execute(delete(EnvironmentalReading))
        res_a = await db.execute(delete(Alert))

        # Reset system_config capture intervals to 1800s (30 minutes)
        cfg_result = await db.execute(delete(SystemConfig))

        await db.commit()
        print(f"  -> Deleted {res_h.rowcount} environmental_history records")
        print(f"  -> Deleted {res_r.rowcount} environmental_readings records")
        print(f"  -> Deleted {res_a.rowcount} alerts records")
        print("Store data successfully purged!")


if __name__ == "__main__":
    asyncio.run(clear_stored_data())

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_config import SystemConfig


class SettingsRepository:
    """Handles global system configuration thresholds persistence (singleton row)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_config(self) -> SystemConfig:
        """Fetch the system config row. Creates default values row if not present."""
        result = await self.db.execute(select(SystemConfig).order_by(SystemConfig.id.asc()).limit(1))
        config = result.scalar_one_or_none()

        if not config:
            # Provision initial row if empty
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
            self.db.add(config)
            await self.db.flush()

        return config

    async def update_config(self, config: SystemConfig) -> SystemConfig:
        """Persist system config changes."""
        self.db.add(config)
        await self.db.flush()
        return config

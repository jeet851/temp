from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.settings_repo import SettingsRepository
from app.schemas.settings import ThresholdUpdate
from app.models.system_config import SystemConfig
from app.websocket.manager import ws_manager
from app.scheduler.tasks import scheduler


class SettingsService:
    """Manages system configuration values and environmental alarm thresholds."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings_repo = SettingsRepository(db)

    async def get_thresholds(self) -> SystemConfig:
        """Fetch global alarm thresholds."""
        return await self.settings_repo.get_config()

    async def update_thresholds(self, schema: ThresholdUpdate) -> SystemConfig:
        """Update environmental warnings and critical thresholds."""
        config = await self.settings_repo.get_config()

        config.temp_warning = schema.temp_warning
        config.temp_critical = schema.temp_critical
        config.hum_warning = schema.hum_warning
        config.hum_critical = schema.hum_critical
        config.ocr_polling_interval_seconds = schema.ocr_polling_interval_seconds
        config.allow_synthetic_fallback = schema.allow_synthetic_fallback

        updated_config = await self.settings_repo.update_config(config)

        # Broadcast the updated configuration to all connected clients
        await ws_manager.broadcast("thresholds", {
            "tempWarning": updated_config.temp_warning,
            "tempCritical": updated_config.temp_critical,
            "humWarning": updated_config.hum_warning,
            "humCritical": updated_config.hum_critical,
            "ocrPollingIntervalSeconds": updated_config.ocr_polling_interval_seconds,
            "allowSyntheticFallback": updated_config.allow_synthetic_fallback,
        })

        if scheduler.get_job("ocr_capture"):
            scheduler.reschedule_job(
                "ocr_capture", 
                trigger="interval", 
                seconds=updated_config.ocr_polling_interval_seconds
            )

        return updated_config

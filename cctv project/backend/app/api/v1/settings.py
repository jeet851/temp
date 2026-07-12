from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.core.dependencies import get_current_user
from app.schemas.settings import ThresholdRead, ThresholdUpdate
from app.schemas.common import APIResponse
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/thresholds", response_model=APIResponse[ThresholdRead])
async def get_thresholds(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Fetch global temperature and humidity violation thresholds settings."""
    service = SettingsService(db)
    config = await service.get_thresholds()
    return APIResponse(success=True, data=ThresholdRead.from_orm(config))


@router.put("/thresholds", response_model=APIResponse[ThresholdRead])
async def update_thresholds(
    payload: ThresholdUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Update global environmental thresholds configuration settings."""
    service = SettingsService(db)
    config = await service.update_thresholds(payload)
    return APIResponse(success=True, message="Thresholds updated.", data=ThresholdRead.from_orm(config))

from datetime import datetime
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.core.dependencies import get_current_user
from app.schemas.environment import (
    EnvironmentalReadingRead,
    EnvironmentalHistoryRead,
    ManualCaptureRequest,
)
from app.schemas.common import APIResponse, PaginatedResponse, PaginationMeta
from app.services.environment_service import EnvironmentService

router = APIRouter(prefix="/environment", tags=["Environmental Data"])


@router.get("/readings", response_model=APIResponse[list[EnvironmentalReadingRead]])
async def get_readings(
    room_id: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Fetch recent live environmental telemetry readings."""
    service = EnvironmentService(db)
    readings = await service.get_readings(room_id, limit)
    return APIResponse(
        success=True, data=[EnvironmentalReadingRead.from_orm(r) for r in readings]
    )


@router.get("/history", response_model=PaginatedResponse[EnvironmentalHistoryRead])
async def get_history(
    room_id: str | None = None,
    start_date: datetime | None = Query(None, description="ISO 8601 start date timestamp"),
    end_date: datetime | None = Query(None, description="ISO 8601 end date timestamp"),
    risk_level: str | None = Query(None, description="low | medium | high"),
    search_query: str | None = Query(None, description="Keyword search across temp, hum, risk"),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Fetch paginated, filtered hourly compliance snapshots logs history."""
    service = EnvironmentService(db)
    records, total = await service.get_history(
        room_id, start_date, end_date, risk_level, search_query, page, per_page
    )

    import math
    pages = math.ceil(total / per_page)

    return PaginatedResponse(
        success=True,
        data=[EnvironmentalHistoryRead.from_orm(r) for r in records],
        meta=PaginationMeta(
            page=page, per_page=per_page, total=total, pages=pages
        ),
    )


@router.post("/history", response_model=APIResponse[EnvironmentalHistoryRead], status_code=status.HTTP_201_CREATED)
async def manual_capture(
    payload: ManualCaptureRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Manually trigger a snapshot frame capture and write to environmental history logs."""
    service = EnvironmentService(db)
    record = await service.trigger_manual_capture(
        payload.room_id, payload.temperature, payload.humidity
    )
    return APIResponse(success=True, message="Manual capture logged.", data=EnvironmentalHistoryRead.from_orm(record))

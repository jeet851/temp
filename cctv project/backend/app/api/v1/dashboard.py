from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.core.dependencies import get_current_user
from app.schemas.dashboard import DashboardSummary
from app.schemas.common import APIResponse
from app.services.dashboard_service import DashboardSummary as DashboardServiceSummary, DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=APIResponse[DashboardSummary])
async def get_summary(
    room_id: str = "room-001",
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Fetch environmental averages, active count indices, and logs lists for dashboard cards."""
    service = DashboardService(db)
    summary = await service.get_summary(room_id)
    return APIResponse(success=True, data=summary)

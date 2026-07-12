from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.core.dependencies import get_current_user
from app.schemas.room import RoomRead
from app.schemas.common import APIResponse
from app.services.environment_service import EnvironmentService

router = APIRouter(prefix="/rooms", tags=["Rooms"])


@router.get("", response_model=APIResponse[list[RoomRead]])
async def get_rooms(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Fetch the list of monitored room zones."""
    service = EnvironmentService(db)
    rooms = await service.get_rooms()
    return APIResponse(success=True, data=[RoomRead.from_orm(r) for r in rooms])

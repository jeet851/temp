from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.core.dependencies import get_current_user
from app.schemas.camera import CameraRead
from app.schemas.common import APIResponse
from app.repositories.camera_repo import CameraRepository

router = APIRouter(prefix="/cameras", tags=["Cameras"])


@router.get("", response_model=APIResponse[list[CameraRead]])
async def get_cameras(
    room_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Fetch CCTV cameras registered on the system, optionally filtered by room."""
    repo = CameraRepository(db)
    if room_id:
        cameras = await repo.list_by_room(room_id)
    else:
        cameras = await repo.list_all()
    return APIResponse(success=True, data=[CameraRead.from_orm(c) for c in cameras])

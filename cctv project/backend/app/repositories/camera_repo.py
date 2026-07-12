from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.camera import Camera


class CameraRepository:
    """Handles database queries for Cameras."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, camera_id: str) -> Camera | None:
        """Fetch a single camera by ID."""
        result = await self.db.execute(select(Camera).where(Camera.id == camera_id))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Camera]:
        """Fetch all cameras."""
        result = await self.db.execute(select(Camera).order_by(Camera.id))
        return list(result.scalars().all())

    async def list_by_room(self, room_id: str) -> list[Camera]:
        """Fetch all cameras associated with a given room ID."""
        result = await self.db.execute(
            select(Camera).where(Camera.room_id == room_id).order_by(Camera.id)
        )
        return list(result.scalars().all())

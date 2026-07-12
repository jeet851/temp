from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.room import Room


class RoomRepository:
    """Handles database queries for Rooms."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, room_id: str) -> Room | None:
        """Fetch a single room by ID."""
        result = await self.db.execute(select(Room).where(Room.id == room_id))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Room]:
        """Fetch all rooms."""
        result = await self.db.execute(select(Room).order_by(Room.id))
        return list(result.scalars().all())

    async def update(self, room: Room) -> Room:
        """Persist updates to a room instance."""
        self.db.add(room)
        await self.db.flush()
        return room

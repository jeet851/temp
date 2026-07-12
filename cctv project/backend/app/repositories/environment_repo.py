from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.environmental_reading import EnvironmentalReading
from app.models.environmental_history import EnvironmentalHistory


class EnvironmentRepository:
    """Handles database queries for sensor telemetry and compliance history logs."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # --- Live Readings ---
    async def create_reading(self, reading: EnvironmentalReading) -> EnvironmentalReading:
        """Create a new live telemetry reading."""
        self.db.add(reading)
        await self.db.flush()
        return reading

    async def get_latest_reading(self, room_id: str) -> EnvironmentalReading | None:
        """Fetch the most recent reading for a given room ID."""
        result = await self.db.execute(
            select(EnvironmentalReading)
            .where(EnvironmentalReading.room_id == room_id)
            .order_by(EnvironmentalReading.timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_recent_readings(self, room_id: str | None = None, limit: int = 50) -> list[EnvironmentalReading]:
        """Fetch the latest `limit` readings, optionally filtered by room."""
        query = select(EnvironmentalReading).order_by(EnvironmentalReading.timestamp.desc()).limit(limit)
        if room_id:
            query = query.where(EnvironmentalReading.room_id == room_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def delete_readings_older_than(self, days: int) -> int:
        """Purge live telemetry readings older than `days` retention period."""
        cutoff = datetime.now() - timedelta(days=days)
        # Using select followed by delete to work across dialects cleanly
        result = await self.db.execute(
            select(EnvironmentalReading).where(EnvironmentalReading.timestamp < cutoff)
        )
        old_readings = result.scalars().all()
        count = len(old_readings)
        for r in old_readings:
            await self.db.delete(r)
        await self.db.flush()
        return count

    # --- Hourly History ---
    async def create_history(self, history: EnvironmentalHistory) -> EnvironmentalHistory:
        """Create a new hourly compliance snapshot record."""
        self.db.add(history)
        await self.db.flush()
        return history

    async def get_history_by_id(self, history_id: str) -> EnvironmentalHistory | None:
        """Fetch a single compliance history log entry by ID."""
        result = await self.db.execute(
            select(EnvironmentalHistory).where(EnvironmentalHistory.id == history_id)
        )
        return result.scalar_one_or_none()

    def _build_history_query(
        self,
        room_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        risk_level: str | None = None,
        search_query: str | None = None,
    ):
        query = select(EnvironmentalHistory)
        filters = []

        if room_id:
            filters.append(EnvironmentalHistory.room_id == room_id)
        if start_date:
            filters.append(EnvironmentalHistory.timestamp >= start_date)
        if end_date:
            filters.append(EnvironmentalHistory.timestamp <= end_date)
        if risk_level and risk_level.lower() != "all":
            filters.append(EnvironmentalHistory.risk_level == risk_level.lower())
        
        if search_query:
            search_pattern = f"%{search_query}%"
            # Support fuzzy search over risk, formatted string fields
            filters.append(
                or_(
                    EnvironmentalHistory.risk_level.like(search_pattern),
                    func.cast(EnvironmentalHistory.temperature, func.String).like(search_pattern),
                    func.cast(EnvironmentalHistory.humidity, func.String).like(search_pattern),
                )
            )

        if filters:
            query = query.where(and_(*filters))

        return query

    async def list_history(
        self,
        room_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        risk_level: str | None = None,
        search_query: str | None = None,
        page: int = 1,
        per_page: int = 10,
    ) -> tuple[list[EnvironmentalHistory], int]:
        """Fetch a paginated, filtered, and searched list of history records."""
        base_query = self._build_history_query(room_id, start_date, end_date, risk_level, search_query)
        
        # Get total count
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        # Fetch records
        offset = (page - 1) * per_page
        records_query = base_query.order_by(EnvironmentalHistory.timestamp.desc()).offset(offset).limit(per_page)
        records_result = await self.db.execute(records_query)
        records = list(records_result.scalars().all())

        return records, total

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditRepository:
    """Handles immutable logging records insertion for compliance tracking."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, log: AuditLog) -> AuditLog:
        """Create an append-only audit log entry."""
        self.db.add(log)
        await self.db.flush()
        return log

    async def list_recent(self, limit: int = 100) -> list[AuditLog]:
        """Fetch the most recent `limit` audit trail logs."""
        result = await self.db.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

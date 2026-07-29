"""
VisionGuard — Audit Log ORM Model.

Immutable append-only table tracking user actions
for compliance and security auditing.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AuditLog(Base):
    """Immutable audit trail entry."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_action", "action"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(
        String(60), nullable=False
    )  # login | logout | settings_change | export | alert_ack | error
    resource: Mapped[str | None] = mapped_column(String(120), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action}: {self.resource}>"

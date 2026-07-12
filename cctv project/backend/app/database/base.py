"""
VisionGuard — SQLAlchemy Declarative Base.

All ORM models inherit from this base class.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass

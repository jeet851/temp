from typing import Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standard success/error API response model."""

    success: bool
    data: T | None = None
    message: str = "OK"


class PaginationMeta(BaseModel):
    """Metadata detailing list pagination state."""

    page: int
    per_page: int
    total: int
    pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated collection payload wrapper."""

    success: bool
    data: list[T]
    meta: PaginationMeta
    message: str = "OK"

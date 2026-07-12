import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Common fields for user management."""

    full_name: str = Field(..., max_length=120)
    username: str = Field(..., max_length=60)
    email: EmailStr
    role: str = "operator"  # admin | operator | viewer
    status: str = "active"  # active | disabled


class UserCreate(UserBase):
    """Payload to provision a new user."""

    password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    """Payload to modify an existing user."""

    full_name: str | None = None
    email: EmailStr | None = None
    role: str | None = None
    status: str | None = None
    password: str | None = Field(None, min_length=6)


class UserRead(UserBase):
    """Serialized user representation for API outputs."""

    id: uuid.UUID
    last_login: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

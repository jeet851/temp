import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.core.dependencies import require_role
from app.schemas.user import UserRead, UserCreate, UserUpdate
from app.schemas.common import APIResponse
from app.services.user_service import UserService

router = APIRouter(
    prefix="/users",
    tags=["Users Management"],
    dependencies=[Depends(require_role("admin"))]
)


@router.get("", response_model=APIResponse[list[UserRead]])
async def list_users(db: AsyncSession = Depends(get_db)):
    """Fetch the list of registered user accounts (Admin only)."""
    service = UserService(db)
    users = await service.list_users()
    return APIResponse(success=True, data=[UserRead.from_orm(u) for u in users])


@router.post("", response_model=APIResponse[UserRead], status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Provision a new user account profile (Admin only)."""
    service = UserService(db)
    user = await service.create_user(payload)
    return APIResponse(success=True, message="User created.", data=UserRead.from_orm(user))


@router.put("/{user_id}", response_model=APIResponse[UserRead])
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Modify details of a user account (Admin only)."""
    service = UserService(db)
    user = await service.update_user(user_id, payload)
    return APIResponse(success=True, message="User updated.", data=UserRead.from_orm(user))


@router.delete("/{user_id}", response_model=APIResponse[UserRead])
async def disable_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Soft-disable access credentials for a user account (Admin only)."""
    service = UserService(db)
    user = await service.disable_user(user_id)
    return APIResponse(success=True, message="User account deactivated.", data=UserRead.from_orm(user))

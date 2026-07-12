import uuid
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    """Manages CRUD logic for User profiles and accounts administration."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)

    async def get_user(self, user_id: uuid.UUID) -> User:
        """Fetch user by ID. Raises 404 if not found."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found."
            )
        return user

    async def list_users(self) -> list[User]:
        """Fetch all user accounts."""
        return await self.user_repo.list_all()

    async def create_user(self, schema: UserCreate) -> User:
        """Provision a new user account with hashed password credentials."""
        existing_email = await self.user_repo.get_by_email(schema.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address already registered."
            )

        existing_username = await self.user_repo.get_by_username(schema.username)
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken."
            )

        user = User(
            full_name=schema.full_name,
            username=schema.username,
            email=schema.email,
            password_hash=hash_password(schema.password),
            role=schema.role,
            status=schema.status
        )
        return await self.user_repo.create(user)

    async def update_user(self, user_id: uuid.UUID, schema: UserUpdate) -> User:
        """Modify an existing user's details."""
        user = await self.get_user(user_id)

        if schema.full_name is not None:
            user.full_name = schema.full_name
        if schema.email is not None:
            # Check unique email
            if schema.email != user.email:
                existing = await self.user_repo.get_by_email(schema.email)
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email address already registered."
                    )
            user.email = schema.email
        if schema.role is not None:
            user.role = schema.role
        if schema.status is not None:
            user.status = schema.status
        if schema.password is not None:
            user.password_hash = hash_password(schema.password)

        return await self.user_repo.update(user)

    async def disable_user(self, user_id: uuid.UUID) -> User:
        """Soft-disable a user's login session access."""
        user = await self.get_user(user_id)
        user.status = "disabled"
        return await self.user_repo.update(user)
class_user_service = UserService

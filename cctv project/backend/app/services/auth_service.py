import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.repositories.user_repo import UserRepository
from app.models.user import User


class AuthService:
    """Manages credentials handshake verification and session tokens lifecycle."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)

    async def authenticate_user(self, email: str, password: str) -> User:
        """
        Verify credentials and return user if active.
        
        Raises:
            HTTPException 401: On incorrect credentials or inactive accounts.
        """
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password.",
            )

        if user.status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account has been disabled.",
            )

        # Check password
        if not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password.",
            )

        # Update last login time
        user.last_login = datetime.now(timezone.utc)
        await self.user_repo.update(user)
        return user

    def generate_tokens(self, user: User) -> dict:
        """Create token payload dictionary containing access and refresh tokens."""
        claims = {"sub": str(user.id), "role": user.role, "email": user.email}
        return {
            "access_token": create_access_token(claims),
            "refresh_token": create_refresh_token(claims),
            "token_type": "bearer"
        }

    async def refresh_session(self, refresh_token: str) -> dict:
        """
        Issue a new access token using a valid refresh token.
        
        Raises:
            HTTPException 401: On invalid or expired refresh tokens.
        """
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session refresh token.",
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims payload.",
            )

        user = await self.user_repo.get_by_id(uuid.UUID(user_id))
        if not user or user.status != "active":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user status changed or not found.",
            )

        # Generate new tokens
        return self.generate_tokens(user)

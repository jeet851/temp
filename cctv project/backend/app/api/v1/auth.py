from fastapi import APIRouter, Depends, Response, status, Cookie
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, PasswordChangeRequest
from app.schemas.user import UserRead
from app.schemas.common import APIResponse
from app.services.auth_service import AuthService
from app.core.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=APIResponse[TokenResponse])
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate credentials and issue authorization tokens."""
    auth_service = AuthService(db)
    user = await auth_service.authenticate_user(payload.email, payload.password)
    tokens = auth_service.generate_tokens(user)
    
    # Store refresh token in secure httpOnly cookie (standard production pattern)
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 3600  # 7 days
    )
    
    return APIResponse(
        success=True,
        message="Login successful.",
        data=TokenResponse(**tokens)
    )


@router.post("/refresh", response_model=APIResponse[TokenResponse])
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db)
):
    """Obtain a new access token using the session refresh token cookie."""
    if not refresh_token:
        # Fallback to authorization headers if needed
        pass
        
    auth_service = AuthService(db)
    tokens = await auth_service.refresh_session(refresh_token)
    
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 3600
    )
    
    return APIResponse(
        success=True,
        message="Session tokens refreshed.",
        data=TokenResponse(**tokens)
    )


@router.post("/logout", response_model=APIResponse[None])
async def logout(response: Response):
    """Clear session authorization cookies."""
    response.delete_cookie("refresh_token")
    return APIResponse(
        success=True,
        message="Logout successful.",
        data=None
    )


@router.get("/me", response_model=APIResponse[UserRead])
async def get_me(current_user: User = Depends(get_current_user)):
    """Fetch the authenticated user account profile details."""
    return APIResponse(
        success=True,
        message="Current user profile fetched.",
        data=UserRead.from_orm(current_user)
    )


@router.put("/password", response_model=APIResponse[None])
async def change_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change the authenticated operator's password."""
    if not verify_password(payload.old_password, current_user.password_hash):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect old password verification."
        )
        
    current_user.password_hash = hash_password(payload.new_password)
    db.add(current_user)
    await db.flush()
    
    return APIResponse(
        success=True,
        message="Password updated successfully.",
        data=None
    )

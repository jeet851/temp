from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Payload to authorize an administrative operator."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Authorization tokens issued to the authenticated operator."""

    access_token: str
    token_type: str = "bearer"
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    """Payload to request password update."""

    old_password: str
    new_password: str = Field(..., min_length=6)

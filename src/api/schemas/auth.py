from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreateRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Unique alphanumeric username (3-50 characters, letters, digits, '-', '_').",
        examples=["operator_jane", "alice_ops"],
    )
    email: EmailStr = Field(
        ...,
        description="Valid RFC-compliant email address.",
        examples=["jane.doe@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plaintext password (min 8 chars, at least one letter and one number).",
        examples=["SecurePass123!"],
    )
    role: Literal["admin", "operator", "viewer"] = Field(
        default="operator",
        description="Assigned RBAC role: 'admin', 'operator', or 'viewer'.",
        examples=["operator"],
    )

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if not any(c.isalpha() for c in v) or not any(c.isdigit() or not c.isalnum() for c in v):
            raise ValueError(
                "Password must contain at least one letter and at least one digit or special character."
            )
        return v


class LoginRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Username or email address.",
        examples=["admin"],
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="User password.",
        examples=["adminpassword123"],
    )


class RefreshTokenRequest(BaseModel):
    refresh_token: str | None = Field(
        default=None,
        description="Valid signed JWT refresh token (optional if provided via HttpOnly cookie).",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="Signed JWT access token.")
    token_type: str = Field(default="bearer", description="Token scheme.")
    expires_in: int = Field(..., description="Lifetime in seconds.")
    refresh_token: str | None = Field(default=None, description="Signed JWT refresh token.")
    user_id: str = Field(..., description="Authenticated user ID.")
    role: str = Field(..., description="Authenticated role.")


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: str = Field(..., description="User ID.")
    username: str = Field(..., description="Username.")
    email: str = Field(..., description="Email address.")
    role: str = Field(..., description="Role.")
    created_at: datetime = Field(..., description="Registration timestamp.")


class PrincipalResponse(BaseModel):
    principal_id: str = Field(..., description="Caller principal ID.")
    role: str = Field(..., description="Caller role.")
    tenant_id: str | None = Field(None, description="Current tenant/project ID if set.")
    scopes: list[str] = Field(default_factory=list, description="Permitted action scopes.")
    auth_mode: str = Field(..., description="Authentication mode used (jwt, api_key).")


class KeyRotationRequest(BaseModel):
    project_id: str = Field(
        ..., description="Target project ID.", examples=["00000000-0000-0000-0000-000000000001"]
    )
    old_key_id: str = Field(
        ..., description="Key ID to rotate out.", examples=["00000000-0000-0000-0000-000000000002"]
    )


class KeyRotationResponse(BaseModel):
    project_id: str = Field(..., description="Target project ID.")
    new_key_id: str = Field(..., description="New key identifier.")
    new_api_key: str = Field(..., description="New raw API key value.")
    revoked_key_id: str = Field(..., description="Revoked key identifier.")

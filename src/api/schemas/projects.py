from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.api.schemas.common import PaginatedResponse


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Display project name.")
    slug: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern="^[a-z0-9-]+$",
        description="URL-safe unique identifier for project.",
    )
    description: str | None = Field(None, max_length=500, description="Project description.")


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    project_id: UUID = Field(..., description="Unique project UUID.")
    name: str = Field(..., description="Project name.")
    slug: str = Field(..., description="Project slug.")
    description: str | None = Field(None, description="Description.")
    created_at: datetime = Field(..., description="Creation timestamp.")


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Key description / label.")
    role: str = Field(
        default="operator", description="Principal role: 'admin', 'operator', 'viewer'."
    )
    scopes: list[str] = Field(
        default_factory=lambda: ["*"], description="Authorized action scopes."
    )


class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key_id: UUID = Field(..., description="API key UUID.")
    project_id: UUID = Field(..., description="Owning project UUID.")
    name: str = Field(..., description="Key label.")
    key_prefix: str = Field(..., description="Key prefix preview (e.g. te_live_abc123...).")
    role: str = Field(..., description="Assigned role.")
    scopes: list[str] = Field(..., description="Assigned scopes.")
    created_at: datetime = Field(..., description="Creation timestamp.")
    last_used_at: datetime | None = Field(None, description="Most recent usage timestamp.")


class ApiKeyCreatedResponse(ApiKeyResponse):
    plain_key: str = Field(
        ...,
        description="Plaintext API key. Copy and store securely; it will NOT be shown again.",
    )


ProjectListResponse = PaginatedResponse[ProjectResponse]
ApiKeyListResponse = PaginatedResponse[ApiKeyResponse]

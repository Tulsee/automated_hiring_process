from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterCandidateRequest(BaseModel):
    """Candidate self-signup. Administration users are created by an admin."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    kind: str
    role: str | None = None
    is_superadmin: bool = False
    active: bool = True
    # The effective permissions, resolved from the role (every permission for
    # the superadmin). Empty for candidates.
    permissions: list[str] = []
    created_at: datetime | None = None


class CreateUserRequest(BaseModel):
    """An administration user, created by someone with users:manage."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=1)
    # The role whose permissions this user gets. Omit for a candidate account.
    role: str | None = None
    kind: str = "administration"


class UpdateUserRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    active: bool | None = None
    password: str | None = Field(None, min_length=8)


class RoleRequest(BaseModel):
    name: str = Field(..., min_length=1, example="recruiter")
    description: str = ""
    permissions: list[str] = Field(default_factory=list)


class RoleUpdateRequest(BaseModel):
    description: str | None = None
    permissions: list[str] | None = None


class RoleResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    permissions: list[str] = []
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PermissionInfo(BaseModel):
    name: str
    description: str


class PermissionCatalogue(BaseModel):
    permissions: list[PermissionInfo]

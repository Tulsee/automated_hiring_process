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


class UserProfile(BaseModel):
    """The editable, non-security parts of an account."""

    phone: str | None = None
    location: str | None = None
    headline: str | None = None
    bio: str | None = None
    # A small avatar, stored as a base64 data URL (data:image/...;base64,...).
    photo: str | None = None


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
    profile: UserProfile = UserProfile()
    # True when this account has a profile change awaiting superadmin approval.
    has_pending_changes: bool = False
    created_at: datetime | None = None


class ProfileUpdateRequest(BaseModel):
    """What any user may change about their own profile."""

    name: str | None = Field(None, min_length=1)
    email: EmailStr | None = None
    phone: str | None = None
    location: str | None = None
    headline: str | None = None
    bio: str | None = None
    photo: str | None = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class ProfileUpdateResult(BaseModel):
    # applied -> changes took effect now; pending -> awaiting superadmin approval
    status: str
    user: UserResponse | None = None
    request_id: str | None = None


class ChangeRequestResponse(BaseModel):
    id: str
    user_id: str
    user_name: str | None = None
    user_email: str | None = None
    # field -> {from, to}
    changes: dict = {}
    status: str
    created_at: datetime | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None


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

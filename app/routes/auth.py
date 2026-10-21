"""Authentication and administration of users and roles.

Split by audience:

* public  - login, and candidate self-signup;
* any signed-in user - their own account (`/auth/me`);
* roles:manage - creating and editing roles, and the permission catalogue;
* users:manage - creating and editing administration users.

Role and user management requires a permission rather than being superadmin-
only, so the superadmin can delegate it; but the permissions that grant it
(`roles:manage`, `users:manage`) are themselves only ever handed out by the
superadmin, who is the only one that starts with them.
"""

import logging

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import (
    get_current_user,
    require_any_permission,
    require_permission,
    require_superadmin,
)
from app.core.security import PasswordTooLong, hash_password
from app.db.mongodb import roles_collection, users_collection
from app.models.role import create_role_document
from app.models.user import KIND_ADMINISTRATION, KIND_CANDIDATE
from app.schemas.auth import (
    ChangeRequestResponse,
    CreateUserRequest,
    LoginRequest,
    PasswordChangeRequest,
    PermissionCatalogue,
    PermissionInfo,
    ProfileUpdateRequest,
    ProfileUpdateResult,
    RegisterCandidateRequest,
    RoleRequest,
    RoleResponse,
    RoleUpdateRequest,
    TokenResponse,
    UpdateUserRequest,
    UserResponse,
)
from app.services import profiles
from app.services.profiles import ProfileError
from app.core.security import create_access_token
from app.services.auth_service import (
    authenticate,
    create_user,
    get_user_by_email,
    user_public,
)
from app.services.permissions import (
    PERMISSIONS,
    UnknownPermission,
    validate_permissions,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_for(user: dict) -> str:
    # The kind and superadmin flag ride in the token so a request can be
    # rejected before any lookup; permissions are resolved fresh, not here.
    return create_access_token(
        subject=str(user["_id"]),
        claims={
            "kind": user.get("kind"),
            "is_superadmin": user.get("is_superadmin", False),
        },
    )


# --------------------------------------------------------------- public

@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest):
    user = await authenticate(data.email, data.password)

    if not user:
        # One message for both wrong email and wrong password, so the endpoint
        # does not reveal which addresses have accounts.
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    return TokenResponse(
        access_token=_token_for(user),
        user=UserResponse(**await user_public(user)),
    )


@router.post("/register", response_model=TokenResponse)
async def register_candidate(data: RegisterCandidateRequest):
    """Candidate self-signup. Only ever creates a candidate account.

    Administration accounts cannot be made this way - they come from an admin
    with users:manage - so this endpoint can be public without letting anyone
    grant themselves privileges.
    """
    if await get_user_by_email(data.email):
        raise HTTPException(
            status_code=409, detail="An account with this email already exists"
        )

    try:
        user = await create_user(
            email=data.email,
            password=data.password,
            name=data.name,
            kind=KIND_CANDIDATE,
        )
    except PasswordTooLong as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return TokenResponse(
        access_token=_token_for(user),
        user=UserResponse(**await user_public(user)),
    )


# --------------------------------------------------------------- self

async def _me_response(user: dict) -> UserResponse:
    response = UserResponse(**await user_public(user))
    response.has_pending_changes = await profiles.has_pending(user["_id"])
    return response


@router.get("/me", response_model=UserResponse)
async def me(user: dict = Depends(get_current_user)):
    return await _me_response(user)


@router.patch("/me/profile", response_model=ProfileUpdateResult)
async def update_my_profile(
    data: ProfileUpdateRequest, user: dict = Depends(get_current_user)
):
    """Edit your own profile.

    A candidate's (or the superadmin's) changes apply immediately; an
    administration user's are queued for superadmin approval.
    """
    try:
        result = await profiles.update_own_profile(
            user, data.model_dump(exclude_unset=True)
        )
    except ProfileError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    if result["status"] == "pending":
        return ProfileUpdateResult(status="pending", request_id=result["request_id"])

    fresh = await users_collection.find_one({"_id": user["_id"]})
    return ProfileUpdateResult(status="applied", user=await _me_response(fresh))


@router.post("/me/password")
async def change_my_password(
    data: PasswordChangeRequest, user: dict = Depends(get_current_user)
):
    """Change your own password immediately (administrators included)."""
    try:
        await profiles.change_password(
            user, data.current_password, data.new_password
        )
    except ProfileError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {"status": "changed"}


# ----------------------------------------------- admin change-request approvals

def _change_request_response(request: dict) -> ChangeRequestResponse:
    return ChangeRequestResponse(
        id=str(request["_id"]),
        user_id=request.get("user_id", ""),
        user_name=request.get("user_name"),
        user_email=request.get("user_email"),
        changes=request.get("changes", {}),
        status=request.get("status", "pending"),
        created_at=request.get("created_at"),
        decided_by=request.get("decided_by"),
        decided_at=request.get("decided_at"),
    )


@router.get("/change-requests", response_model=list[ChangeRequestResponse])
async def list_change_requests(_: dict = Depends(require_superadmin)):
    """Pending administration profile changes awaiting the superadmin."""
    return [_change_request_response(r) for r in await profiles.list_pending()]


@router.post("/change-requests/{request_id}/approve")
async def approve_change_request(
    request_id: str, actor: dict = Depends(require_superadmin)
):
    try:
        return await profiles.approve(request_id, actor.get("email"))
    except ProfileError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/change-requests/{request_id}/reject")
async def reject_change_request(
    request_id: str, actor: dict = Depends(require_superadmin)
):
    try:
        return await profiles.reject(request_id, actor.get("email"))
    except ProfileError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


# --------------------------------------------------------------- roles

@router.get("/permissions", response_model=PermissionCatalogue)
async def list_permissions(
    _: dict = Depends(require_permission("roles:manage")),
):
    """The full catalogue, so the role editor can list what it may grant."""
    return PermissionCatalogue(
        permissions=[
            PermissionInfo(name=name, description=description)
            for name, description in PERMISSIONS.items()
        ]
    )


def _role_response(role: dict) -> RoleResponse:
    return RoleResponse(
        id=str(role["_id"]),
        name=role["name"],
        description=role.get("description", ""),
        permissions=role.get("permissions", []),
        created_by=role.get("created_by"),
        created_at=role.get("created_at"),
        updated_at=role.get("updated_at"),
    )


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    # A user manager needs to read roles to assign one, so either permission
    # may list them; only roles:manage may create or edit them (below).
    _: dict = Depends(require_any_permission("roles:manage", "users:manage")),
):
    return [
        _role_response(role) async for role in roles_collection.find()
    ]


@router.post("/roles", response_model=RoleResponse)
async def create_role(
    data: RoleRequest,
    actor: dict = Depends(require_permission("roles:manage")),
):
    if await roles_collection.find_one({"name": data.name.strip()}):
        raise HTTPException(
            status_code=409, detail=f"A role named '{data.name}' already exists"
        )

    try:
        permissions = validate_permissions(data.permissions)
    except UnknownPermission as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    document = create_role_document(
        name=data.name,
        permissions=permissions,
        description=data.description,
        created_by=str(actor["_id"]),
    )

    result = await roles_collection.insert_one(document)
    document["_id"] = result.inserted_id

    logger.info("Role created: %s with %d permissions", data.name, len(permissions))

    return _role_response(document)


@router.patch("/roles/{name}", response_model=RoleResponse)
async def update_role(
    name: str,
    data: RoleUpdateRequest,
    _: dict = Depends(require_permission("roles:manage")),
):
    role = await roles_collection.find_one({"name": name})

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    updates: dict = {}

    if data.description is not None:
        updates["description"] = data.description.strip()

    if data.permissions is not None:
        try:
            updates["permissions"] = validate_permissions(data.permissions)
        except UnknownPermission as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    if not updates:
        raise HTTPException(status_code=400, detail="No changes were sent")

    from datetime import datetime

    updates["updated_at"] = datetime.utcnow()

    await roles_collection.update_one({"name": name}, {"$set": updates})

    return _role_response(await roles_collection.find_one({"name": name}))


@router.delete("/roles/{name}")
async def delete_role(
    name: str,
    _: dict = Depends(require_permission("roles:manage")),
):
    # A role still assigned to someone cannot be deleted, or those users would
    # silently lose all permissions and be impossible to diagnose.
    in_use = await users_collection.count_documents({"role": name})

    if in_use:
        raise HTTPException(
            status_code=409,
            detail=f"{in_use} user(s) still have this role; reassign them first",
        )

    result = await roles_collection.delete_one({"name": name})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Role not found")

    return {"deleted": name}


# --------------------------------------------------------------- users

@router.get("/users", response_model=list[UserResponse])
async def list_users(_: dict = Depends(require_permission("users:manage"))):
    return [
        UserResponse(**await user_public(user))
        async for user in users_collection.find()
    ]


@router.post("/users", response_model=UserResponse)
async def create_administration_user(
    data: CreateUserRequest,
    _: dict = Depends(require_permission("users:manage")),
):
    if data.kind not in (KIND_ADMINISTRATION, KIND_CANDIDATE):
        raise HTTPException(status_code=400, detail="Unknown user kind")

    if await get_user_by_email(data.email):
        raise HTTPException(
            status_code=409, detail="An account with this email already exists"
        )

    if data.role is not None:
        if not await roles_collection.find_one({"name": data.role}):
            raise HTTPException(
                status_code=400, detail=f"No role named '{data.role}'"
            )

    try:
        user = await create_user(
            email=data.email,
            password=data.password,
            name=data.name,
            kind=data.kind,
            role=data.role if data.kind == KIND_ADMINISTRATION else None,
        )
    except PasswordTooLong as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return UserResponse(**await user_public(user))


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    data: UpdateUserRequest,
    actor: dict = Depends(require_permission("users:manage")),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user id")

    user = await users_collection.find_one({"_id": ObjectId(user_id)})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.get("is_superadmin"):
        # The superadmin's role and active state are not something another
        # admin may change; that account is the root of trust.
        raise HTTPException(
            status_code=403, detail="The superadmin account cannot be modified here"
        )

    updates: dict = {}

    if data.name is not None:
        updates["name"] = data.name.strip()

    if data.role is not None:
        if data.role and not await roles_collection.find_one({"name": data.role}):
            raise HTTPException(
                status_code=400, detail=f"No role named '{data.role}'"
            )
        updates["role"] = data.role or None

    if data.active is not None:
        updates["active"] = data.active

    if data.password is not None:
        try:
            updates["password_hash"] = hash_password(data.password)
        except PasswordTooLong as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    if not updates:
        raise HTTPException(status_code=400, detail="No changes were sent")

    from datetime import datetime

    updates["updated_at"] = datetime.utcnow()

    await users_collection.update_one(
        {"_id": ObjectId(user_id)}, {"$set": updates}
    )

    return UserResponse(
        **await user_public(await users_collection.find_one({"_id": ObjectId(user_id)}))
    )

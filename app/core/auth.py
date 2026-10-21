"""FastAPI guards that turn a bearer token into an authorised principal.

A route states what it needs and gets a dependency:

    @router.post("/", dependencies=[Depends(require_permission("jobs:write"))])

Four guards, from weakest to strongest:

* `get_current_user` - a signed-in user of any kind.
* `require_kind("administration")` - an administration user (any role).
* `require_permission("jobs:write")` - holds that permission (superadmin
  always does).
* `require_superadmin` - the superadmin alone.

`optional_user` is the exception: it never rejects, so a route can serve the
public but personalise for a signed-in one.
"""

import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import TokenError, decode_access_token
from app.models.user import KIND_ADMINISTRATION
from app.services.auth_service import effective_permissions, get_user_by_id

logger = logging.getLogger(__name__)

# auto_error=False so the same scheme can back both required and optional
# guards; the required ones raise 401 themselves with a clear message.
_bearer = HTTPBearer(auto_error=False)

UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Sign in to continue",
    headers={"WWW-Authenticate": "Bearer"},
)


async def _user_from_credentials(
    credentials: HTTPAuthorizationCredentials | None,
) -> dict | None:
    if credentials is None:
        return None

    try:
        payload = decode_access_token(credentials.credentials)
    except TokenError:
        return None

    user = await get_user_by_id(payload.get("sub", ""))

    # A token for a deleted or since-disabled account is worthless, even
    # though its signature is still valid.
    if not user or not user.get("active", True):
        return None

    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    user = await _user_from_credentials(credentials)

    if user is None:
        raise UNAUTHENTICATED

    return user


async def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict | None:
    """The signed-in user, or None. Never rejects."""
    return await _user_from_credentials(credentials)


def require_kind(kind: str):
    async def guard(user: dict = Depends(get_current_user)) -> dict:
        # The superadmin is administration and is never shut out of it.
        if user.get("kind") != kind and not user.get("is_superadmin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This area is for {kind} users",
            )

        return user

    return guard


def require_permission(permission: str):
    async def guard(user: dict = Depends(get_current_user)) -> dict:
        if user.get("is_superadmin"):
            return user

        if permission not in await effective_permissions(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not have permission to {permission}",
            )

        return user

    return guard


def require_any_permission(*permissions: str):
    """Holds *at least one* of these permissions (superadmin always does).

    For an action that more than one role legitimately needs - e.g. listing
    roles, which both a role manager and a user manager must do (the latter to
    assign a role to a user).
    """

    async def guard(user: dict = Depends(get_current_user)) -> dict:
        if user.get("is_superadmin"):
            return user

        held = await effective_permissions(user)

        if not any(permission in held for permission in permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You need one of: " + ", ".join(permissions)
                ),
            )

        return user

    return guard


async def require_superadmin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the superadmin can do this",
        )

    return user


# Convenience for the common administration case.
require_administration = require_kind(KIND_ADMINISTRATION)


def current_request_user(request: Request) -> dict | None:
    """The user resolved for this request, if a guard already ran."""
    return getattr(request.state, "user", None)

"""Creating, authenticating and describing users.

The one piece of judgement here is how a user's *effective* permissions are
resolved: the superadmin has all of them, an administration user has whatever
their role currently grants (looked up fresh, so editing a role takes effect
immediately), and a candidate has none.
"""

import logging

from bson import ObjectId

from app.core.security import hash_password, verify_password
from app.db.mongodb import roles_collection, users_collection
from app.models.user import KIND_ADMINISTRATION, create_user_document
from app.services.permissions import ALL_PERMISSIONS

logger = logging.getLogger(__name__)


async def role_permissions(role_name: str | None) -> list[str]:
    if not role_name:
        return []

    role = await roles_collection.find_one({"name": role_name})

    return list(role.get("permissions", [])) if role else []


async def effective_permissions(user: dict) -> list[str]:
    """What this user is actually allowed to do, right now."""
    if user.get("is_superadmin"):
        return sorted(ALL_PERMISSIONS)

    return await role_permissions(user.get("role"))


async def user_public(user: dict) -> dict:
    """A user as the API exposes it - never including the password hash."""
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "name": user.get("name", ""),
        "kind": user.get("kind"),
        "role": user.get("role"),
        "is_superadmin": user.get("is_superadmin", False),
        "active": user.get("active", True),
        "permissions": await effective_permissions(user),
        "profile": {
            "phone": user.get("phone"),
            "location": user.get("location"),
            "headline": user.get("headline"),
            "bio": user.get("bio"),
            "photo": user.get("photo"),
        },
        "created_at": user.get("created_at"),
    }


async def get_user_by_email(email: str) -> dict | None:
    return await users_collection.find_one({"email": email.strip().lower()})


async def get_user_by_id(user_id: str) -> dict | None:
    if not ObjectId.is_valid(user_id):
        return None

    return await users_collection.find_one({"_id": ObjectId(user_id)})


async def authenticate(email: str, password: str) -> dict | None:
    """Return the user on a correct email+password, else None.

    A disabled account cannot sign in: the check belongs here so no token is
    ever issued for one, rather than relying on every guard to re-check.
    """
    user = await get_user_by_email(email)

    if not user or not user.get("active", True):
        return None

    if not verify_password(password, user.get("password_hash", "")):
        return None

    return user


async def create_user(
    email: str,
    password: str,
    name: str,
    kind: str,
    role: str | None = None,
    is_superadmin: bool = False,
) -> dict:
    document = create_user_document(
        email=email,
        password_hash=hash_password(password),
        name=name,
        kind=kind,
        role=role,
        is_superadmin=is_superadmin,
    )

    result = await users_collection.insert_one(document)

    document["_id"] = result.inserted_id

    return document


async def ensure_superadmin(
    email: str, password: str, name: str
) -> dict | None:
    """Create the superadmin if it is absent. Idempotent.

    Called on startup. With no password configured it does nothing, so a
    misconfigured deployment fails closed (no account) rather than creating
    one with a blank or guessable password.
    """
    if not password:
        logger.warning(
            "No SUPERADMIN_PASSWORD set; skipping superadmin bootstrap"
        )
        return None

    existing = await get_user_by_email(email)

    if existing:
        return existing

    user = await create_user(
        email=email,
        password=password,
        name=name,
        kind=KIND_ADMINISTRATION,
        role=None,
        is_superadmin=True,
    )

    logger.info("Superadmin account created: %s", email)

    return user

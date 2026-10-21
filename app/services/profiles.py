"""Editing your own account, and the superadmin approval gate for admins.

Two shapes of edit:

* a **candidate** (or the superadmin) edits their profile and it applies at
  once - they own their own details;
* an **administration** user's edit does not apply immediately. It is recorded
  as a *change request* that a superadmin approves or rejects, so the hiring
  team's identities are not changed unsupervised.

Passwords are never part of this: a user always changes their own password
immediately (verifying the current one), administrators included.
"""

import logging
from datetime import datetime

from bson import ObjectId

from app.core.security import hash_password, verify_password
from app.db.mongodb import change_requests_collection, users_collection
from app.models.user import KIND_CANDIDATE
from app.services.auth_service import get_user_by_email
from app.services.notifications import (
    KIND_APPROVAL,
    KIND_APPROVAL_RESULT,
    notify,
    notify_superadmins,
)

logger = logging.getLogger(__name__)

# The fields a user may edit about themselves (never role/kind/superadmin).
PROFILE_FIELDS = ("name", "email", "phone", "location", "headline", "bio", "photo")

PROFILE_ONLY = ("phone", "location", "headline", "bio", "photo")


class ProfileError(ValueError):
    """A rejected profile edit (e.g. an email already in use)."""


def profile_of(user: dict) -> dict:
    return {field: user.get(field) for field in PROFILE_ONLY}


def _requires_approval(user: dict) -> bool:
    """Administration users (but not the superadmin) need approval."""
    if user.get("is_superadmin"):
        return False
    return user.get("kind") != KIND_CANDIDATE


async def _validate_email(new_email: str, user_id) -> None:
    existing = await get_user_by_email(new_email)
    if existing and existing["_id"] != user_id:
        raise ProfileError("An account with this email already exists")


def _clean_changes(user: dict, changes: dict) -> dict:
    """Only the fields that are present and actually different."""
    result = {}
    for field in PROFILE_FIELDS:
        if field not in changes or changes[field] is None:
            continue
        value = changes[field]
        if field == "email":
            value = value.strip().lower()
        if value != user.get(field):
            result[field] = value
    return result


async def apply_changes(user_id, changes: dict) -> None:
    """Write field->value changes onto a user, checking email uniqueness."""
    if "email" in changes:
        await _validate_email(changes["email"], user_id)

    changes = {**changes, "updated_at": datetime.utcnow()}
    await users_collection.update_one({"_id": user_id}, {"$set": changes})


async def update_own_profile(user: dict, changes: dict) -> dict:
    """Apply a candidate's/superadmin's edit now; queue an admin's for approval."""
    diff = _clean_changes(user, changes)

    if not diff:
        return {"status": "applied"}

    if _requires_approval(user):
        # Record the before/after so the superadmin sees exactly what changes.
        detailed = {
            field: {"from": user.get(field), "to": value}
            for field, value in diff.items()
        }
        result = await change_requests_collection.insert_one(
            {
                "user_id": str(user["_id"]),
                "user_name": user.get("name"),
                "user_email": user.get("email"),
                "changes": detailed,
                "status": "pending",
                "created_at": datetime.utcnow(),
            }
        )
        await notify_superadmins(
            KIND_APPROVAL,
            "A profile change needs approval",
            f"{user.get('name') or user.get('email')} requested changes to their profile.",
        )
        return {"status": "pending", "request_id": str(result.inserted_id)}

    await apply_changes(user["_id"], diff)
    return {"status": "applied"}


async def change_password(user: dict, current: str, new: str) -> None:
    if not verify_password(current, user.get("password_hash", "")):
        raise ProfileError("Your current password is incorrect")

    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": hash_password(new), "updated_at": datetime.utcnow()}},
    )


async def has_pending(user_id) -> bool:
    count = await change_requests_collection.count_documents(
        {"user_id": str(user_id), "status": "pending"}
    )
    return count > 0


async def list_pending() -> list[dict]:
    items = [
        request
        async for request in change_requests_collection.find({"status": "pending"})
    ]
    items.sort(key=lambda r: r.get("created_at") or datetime.min, reverse=True)
    return items


async def _load_request(request_id: str) -> dict | None:
    if not ObjectId.is_valid(request_id):
        return None
    return await change_requests_collection.find_one({"_id": ObjectId(request_id)})


async def approve(request_id: str, approver: str | None) -> dict:
    request = await _load_request(request_id)
    if not request:
        raise ProfileError("Change request not found")
    if request["status"] != "pending":
        raise ProfileError("This request has already been decided")

    # {field: {from, to}} -> {field: to}
    changes = {field: change["to"] for field, change in request["changes"].items()}

    if not ObjectId.is_valid(request["user_id"]):
        raise ProfileError("The requesting account no longer exists")

    await apply_changes(ObjectId(request["user_id"]), changes)

    await change_requests_collection.update_one(
        {"_id": request["_id"]},
        {"$set": {"status": "approved", "decided_by": approver, "decided_at": datetime.utcnow()}},
    )

    await notify(
        request["user_id"],
        KIND_APPROVAL_RESULT,
        "Your profile changes were approved",
        "The changes you requested are now live.",
    )

    return {"status": "approved", "request_id": request_id}


async def reject(request_id: str, approver: str | None) -> dict:
    request = await _load_request(request_id)
    if not request:
        raise ProfileError("Change request not found")
    if request["status"] != "pending":
        raise ProfileError("This request has already been decided")

    await change_requests_collection.update_one(
        {"_id": request["_id"]},
        {"$set": {"status": "rejected", "decided_by": approver, "decided_at": datetime.utcnow()}},
    )

    await notify(
        request["user_id"],
        KIND_APPROVAL_RESULT,
        "Your profile changes were not approved",
        "A superadmin reviewed your requested changes and did not apply them.",
    )

    return {"status": "rejected", "request_id": request_id}

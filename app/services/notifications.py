"""In-app notifications: the bell feed, one row per thing a user should see.

Notifications are per *user account*, so an event fans out to the accounts that
care about it: a candidate about their own application, administration users
about new applications to work, superadmins about profile-change requests
awaiting approval. Creating one never fails the thing that triggered it - the
feed is a convenience, not part of the transaction - so every emit swallows and
logs its own errors.
"""

import logging
from datetime import datetime

from bson import ObjectId

from app.db.mongodb import notifications_collection, users_collection

logger = logging.getLogger(__name__)

# Event kinds, so the UI can pick an icon and callers stay consistent.
KIND_APPLICATION = "application"  # candidate: your application moved
KIND_NEW_APPLICATION = "new_application"  # admin: someone applied
KIND_REVIEW = "review"  # admin: an interview is ready to review
KIND_APPROVAL = "approval"  # superadmin: a change request needs a decision
KIND_APPROVAL_RESULT = "approval_result"  # admin: your request was decided


async def notify(
    user_id: str | None,
    kind: str,
    title: str,
    body: str = "",
    link: str | None = None,
) -> None:
    """Add one notification for one user. No-op without a user id."""
    if not user_id:
        return

    try:
        await notifications_collection.insert_one(
            {
                "user_id": str(user_id),
                "kind": kind,
                "title": title,
                "body": body,
                "link": link,
                "read": False,
                "created_at": datetime.utcnow(),
            }
        )
    except Exception as error:  # noqa: BLE001 - never fail the triggering action
        logger.error("Could not create notification for %s: %s", user_id, error)


async def notify_many(user_ids, kind, title, body="", link=None) -> None:
    for user_id in user_ids:
        await notify(user_id, kind, title, body, link)


async def _ids_where(query: dict) -> list[str]:
    return [str(user["_id"]) async for user in users_collection.find(query)]


async def notify_administration(
    kind: str, title: str, body: str = "", link: str | None = None
) -> None:
    """Fan out to every active administration user (including superadmins)."""
    ids = await _ids_where({"kind": "administration", "active": {"$ne": False}})
    await notify_many(ids, kind, title, body, link)


async def notify_superadmins(
    kind: str, title: str, body: str = "", link: str | None = None
) -> None:
    ids = await _ids_where({"is_superadmin": True})
    await notify_many(ids, kind, title, body, link)


async def list_for_user(user_id: str, limit: int = 50) -> dict:
    """A user's notifications, newest first, with the unread count."""
    items = [
        notification
        async for notification in notifications_collection.find(
            {"user_id": str(user_id)}
        )
    ]

    items.sort(key=lambda n: n.get("created_at") or datetime.min, reverse=True)
    items = items[:limit]

    unread = sum(1 for n in items if not n.get("read"))

    return {"unread": unread, "notifications": items}


async def mark_read(user_id: str, notification_id: str) -> bool:
    if not ObjectId.is_valid(notification_id):
        return False

    result = await notifications_collection.update_one(
        {"_id": ObjectId(notification_id), "user_id": str(user_id)},
        {"$set": {"read": True}},
    )
    return result.modified_count > 0


async def mark_all_read(user_id: str) -> int:
    result = await notifications_collection.update_many(
        {"user_id": str(user_id), "read": False},
        {"$set": {"read": True}},
    )
    return result.modified_count

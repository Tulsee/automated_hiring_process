"""The signed-in user's notification feed (the topbar bell)."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.schemas.notification import Notification, NotificationList
from app.services.notifications import (
    list_for_user,
    mark_all_read,
    mark_read,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _to_model(document: dict) -> Notification:
    return Notification(
        id=str(document["_id"]),
        kind=document.get("kind", ""),
        title=document.get("title", ""),
        body=document.get("body", ""),
        link=document.get("link"),
        read=bool(document.get("read")),
        created_at=document.get("created_at"),
    )


@router.get("", response_model=NotificationList)
async def my_notifications(user: dict = Depends(get_current_user)):
    result = await list_for_user(str(user["_id"]))

    return NotificationList(
        unread=result["unread"],
        notifications=[_to_model(n) for n in result["notifications"]],
    )


@router.post("/{notification_id}/read")
async def read_notification(
    notification_id: str, user: dict = Depends(get_current_user)
):
    ok = await mark_read(str(user["_id"]), notification_id)

    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")

    return {"read": notification_id}


@router.post("/read-all")
async def read_all_notifications(user: dict = Depends(get_current_user)):
    count = await mark_all_read(str(user["_id"]))

    return {"marked_read": count}

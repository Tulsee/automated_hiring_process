from datetime import datetime

from pydantic import BaseModel


class Notification(BaseModel):
    id: str
    kind: str
    title: str
    body: str = ""
    link: str | None = None
    read: bool = False
    created_at: datetime | None = None


class NotificationList(BaseModel):
    unread: int
    notifications: list[Notification] = []

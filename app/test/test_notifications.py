"""The in-app notification feed and the events that fill it."""

from datetime import datetime

from bson import ObjectId

from app.services.notifications import (
    KIND_APPLICATION,
    KIND_NEW_APPLICATION,
    list_for_user,
    mark_all_read,
    notify,
    notify_administration,
)


class TestNotifyService:
    async def test_notify_adds_a_row_for_the_user(self, fakes):
        await notify("user-1", KIND_APPLICATION, "Hello", "body")

        result = await list_for_user("user-1")
        assert result["unread"] == 1
        assert result["notifications"][0]["title"] == "Hello"

    async def test_notify_ignores_a_missing_user(self, fakes):
        await notify(None, KIND_APPLICATION, "Nobody")

        assert fakes.notifications.documents == []

    async def test_mark_all_read_clears_the_unread_count(self, fakes):
        await notify("user-1", KIND_APPLICATION, "One")
        await notify("user-1", KIND_APPLICATION, "Two")

        await mark_all_read("user-1")

        assert (await list_for_user("user-1"))["unread"] == 0

    async def test_administration_fan_out_reaches_every_admin(self, fakes):
        fakes.users.documents.append(
            {"_id": ObjectId(), "kind": "administration", "active": True}
        )
        fakes.users.documents.append(
            {"_id": ObjectId(), "kind": "administration", "is_superadmin": True}
        )
        # A candidate account must not be notified of hiring-team events.
        fakes.users.documents.append({"_id": ObjectId(), "kind": "candidate"})

        await notify_administration(KIND_NEW_APPLICATION, "New one")

        assert len(fakes.notifications.documents) == 2


class TestNotificationRoutes:
    async def test_feed_lists_my_notifications_newest_first(
        self, client, fakes, principal
    ):
        uid = str(principal["_id"])
        fakes.notifications.documents.append(
            {
                "_id": ObjectId(),
                "user_id": uid,
                "kind": KIND_APPLICATION,
                "title": "Older",
                "read": False,
                "created_at": datetime(2026, 1, 1),
            }
        )
        fakes.notifications.documents.append(
            {
                "_id": ObjectId(),
                "user_id": uid,
                "kind": KIND_APPLICATION,
                "title": "Newer",
                "read": False,
                "created_at": datetime(2026, 2, 1),
            }
        )
        # Someone else's notification must not leak into my feed.
        fakes.notifications.documents.append(
            {
                "_id": ObjectId(),
                "user_id": "someone-else",
                "kind": KIND_APPLICATION,
                "title": "Not mine",
                "read": False,
                "created_at": datetime(2026, 3, 1),
            }
        )

        body = (await client.get("/notifications")).json()

        assert body["unread"] == 2
        assert [n["title"] for n in body["notifications"]] == ["Newer", "Older"]

    async def test_marking_one_read(self, client, fakes, principal):
        notification_id = ObjectId()
        fakes.notifications.documents.append(
            {
                "_id": notification_id,
                "user_id": str(principal["_id"]),
                "kind": KIND_APPLICATION,
                "title": "Read me",
                "read": False,
                "created_at": datetime.utcnow(),
            }
        )

        response = await client.post(f"/notifications/{notification_id}/read")

        assert response.status_code == 200
        assert (await client.get("/notifications")).json()["unread"] == 0

    async def test_marking_a_missing_one_is_404(self, client, fakes):
        response = await client.post(f"/notifications/{ObjectId()}/read")

        assert response.status_code == 404

    async def test_read_all(self, client, fakes, principal):
        for title in ("a", "b", "c"):
            fakes.notifications.documents.append(
                {
                    "_id": ObjectId(),
                    "user_id": str(principal["_id"]),
                    "kind": KIND_APPLICATION,
                    "title": title,
                    "read": False,
                    "created_at": datetime.utcnow(),
                }
            )

        response = await client.post("/notifications/read-all")

        assert response.json()["marked_read"] == 3
        assert (await client.get("/notifications")).json()["unread"] == 0

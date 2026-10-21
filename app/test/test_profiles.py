"""Self-service profiles, password changes, and the admin approval gate."""

from bson import ObjectId

from app.core.security import hash_password


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def seed_user(fakes, *, kind, email, password="a-good-password", **extra):
    user = {
        "_id": ObjectId(),
        "email": email,
        "name": extra.pop("name", "Person"),
        "kind": kind,
        "role": extra.pop("role", None),
        "is_superadmin": extra.pop("is_superadmin", False),
        "active": True,
        "password_hash": hash_password(password),
        **extra,
    }
    fakes.users.documents.append(user)
    return user


async def login(client, email, password="a-good-password"):
    response = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    return response.json()["access_token"]


class TestCandidateProfile:
    async def test_a_candidate_edit_applies_immediately(
        self, client, fakes, real_auth
    ):
        user = seed_user(fakes, kind="candidate", email="cand@example.com")
        token = await login(client, "cand@example.com")

        response = await client.patch(
            "/auth/me/profile",
            json={"name": "Grace", "headline": "Engineer", "photo": "data:image/png;base64,AAA"},
            headers=auth(token),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "applied"
        assert body["user"]["name"] == "Grace"
        assert body["user"]["profile"]["headline"] == "Engineer"
        # Written through to the record.
        assert user["name"] == "Grace"

    async def test_a_duplicate_email_is_refused(self, client, fakes, real_auth):
        seed_user(fakes, kind="candidate", email="cand@example.com")
        seed_user(fakes, kind="candidate", email="taken@example.com")
        token = await login(client, "cand@example.com")

        response = await client.patch(
            "/auth/me/profile",
            json={"email": "taken@example.com"},
            headers=auth(token),
        )

        assert response.status_code == 400


class TestAdminProfileApproval:
    async def test_an_admin_edit_is_queued_not_applied(
        self, client, fakes, real_auth
    ):
        admin = seed_user(
            fakes, kind="administration", email="admin@example.com", name="Al"
        )
        token = await login(client, "admin@example.com")

        response = await client.patch(
            "/auth/me/profile",
            json={"name": "Alistair"},
            headers=auth(token),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "pending"
        # Not applied yet.
        assert admin["name"] == "Al"
        assert len(fakes.change_requests.documents) == 1

    async def test_me_reports_a_pending_change(self, client, fakes, real_auth):
        seed_user(fakes, kind="administration", email="admin@example.com")
        token = await login(client, "admin@example.com")

        await client.patch(
            "/auth/me/profile", json={"name": "New"}, headers=auth(token)
        )

        me = (await client.get("/auth/me", headers=auth(token))).json()
        assert me["has_pending_changes"] is True

    async def test_superadmin_approves_and_the_change_applies(
        self, client, fakes, real_auth
    ):
        admin = seed_user(
            fakes, kind="administration", email="admin@example.com", name="Al"
        )
        seed_user(
            fakes,
            kind="administration",
            email="boss@example.com",
            is_superadmin=True,
        )

        admin_token = await login(client, "admin@example.com")
        await client.patch(
            "/auth/me/profile", json={"name": "Alistair"}, headers=auth(admin_token)
        )

        boss_token = await login(client, "boss@example.com")
        pending = (
            await client.get("/auth/change-requests", headers=auth(boss_token))
        ).json()
        assert len(pending) == 1

        request_id = pending[0]["id"]
        approved = await client.post(
            f"/auth/change-requests/{request_id}/approve", headers=auth(boss_token)
        )

        assert approved.status_code == 200
        assert admin["name"] == "Alistair"

    async def test_superadmin_rejects_and_nothing_changes(
        self, client, fakes, real_auth
    ):
        admin = seed_user(
            fakes, kind="administration", email="admin@example.com", name="Al"
        )
        seed_user(fakes, kind="administration", email="boss@example.com", is_superadmin=True)

        admin_token = await login(client, "admin@example.com")
        await client.patch(
            "/auth/me/profile", json={"name": "Nope"}, headers=auth(admin_token)
        )

        boss_token = await login(client, "boss@example.com")
        request_id = (
            await client.get("/auth/change-requests", headers=auth(boss_token))
        ).json()[0]["id"]

        await client.post(
            f"/auth/change-requests/{request_id}/reject", headers=auth(boss_token)
        )

        assert admin["name"] == "Al"

    async def test_a_non_superadmin_cannot_see_the_queue(
        self, client, fakes, real_auth
    ):
        seed_user(
            fakes,
            kind="administration",
            email="admin@example.com",
            role="recruiter",
        )
        # recruiter role exists with users:manage, but approvals are superadmin-only
        fakes.roles.documents.append(
            {"_id": ObjectId(), "name": "recruiter", "permissions": ["users:manage"]}
        )
        token = await login(client, "admin@example.com")

        response = await client.get("/auth/change-requests", headers=auth(token))

        assert response.status_code == 403


class TestPasswordChange:
    async def test_an_admin_changes_their_own_password_immediately(
        self, client, fakes, real_auth
    ):
        seed_user(
            fakes,
            kind="administration",
            email="admin@example.com",
            password="old-password",
        )
        token = await login(client, "admin@example.com", "old-password")

        response = await client.post(
            "/auth/me/password",
            json={"current_password": "old-password", "new_password": "new-password-1"},
            headers=auth(token),
        )

        assert response.status_code == 200
        # The new password now works.
        assert await login(client, "admin@example.com", "new-password-1")

    async def test_a_wrong_current_password_is_refused(
        self, client, fakes, real_auth
    ):
        seed_user(fakes, kind="candidate", email="cand@example.com")
        token = await login(client, "cand@example.com")

        response = await client.post(
            "/auth/me/password",
            json={"current_password": "wrong", "new_password": "new-password-1"},
            headers=auth(token),
        )

        assert response.status_code == 400

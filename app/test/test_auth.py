"""Authentication and role-based authorisation.

These run the real guards: the `client` fixture signs every request in as the
superadmin, so here it is cleared and a token is presented explicitly, which is
what exercises `require_permission`, `require_kind` and the login flow.
"""

import pytest
from bson import ObjectId

from app.core import auth as auth_core
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.services.permissions import ALL_PERMISSIONS, validate_permissions
from app.services.permissions import UnknownPermission


# --------------------------------------------------------------- units

class TestPasswordHashing:
    def test_a_hash_verifies_against_its_password(self):
        hashed = hash_password("correct horse battery staple")

        assert verify_password("correct horse battery staple", hashed)

    def test_the_wrong_password_does_not_verify(self):
        hashed = hash_password("secret")

        assert not verify_password("guess", hashed)

    def test_the_hash_is_not_the_password(self):
        assert hash_password("secret") != "secret"

    def test_a_malformed_hash_fails_closed(self):
        # A corrupt stored hash must read as "wrong password", not crash.
        assert not verify_password("secret", "not-a-bcrypt-hash")

    def test_an_over_long_password_is_rejected(self):
        from app.core.security import PasswordTooLong

        with pytest.raises(PasswordTooLong):
            hash_password("x" * 100)


class TestTokens:
    def test_a_token_round_trips_its_claims(self):
        token = create_access_token(
            "user-1", {"kind": "administration", "is_superadmin": True}
        )

        payload = decode_access_token(token)

        assert payload["sub"] == "user-1"
        assert payload["kind"] == "administration"
        assert payload["is_superadmin"] is True

    def test_a_tampered_token_is_rejected(self):
        from app.core.security import TokenError

        token = create_access_token("user-1", {})

        with pytest.raises(TokenError):
            decode_access_token(token + "tampered")

    def test_an_expired_token_is_rejected(self):
        from datetime import timedelta
        from app.core.security import TokenError

        token = create_access_token(
            "user-1", {}, expires_delta=timedelta(seconds=-1)
        )

        with pytest.raises(TokenError, match="expired"):
            decode_access_token(token)


class TestPermissionCatalogue:
    def test_known_permissions_pass_through_deduplicated(self):
        cleaned = validate_permissions(["jobs:read", "jobs:read", "jobs:write"])

        assert cleaned == ["jobs:read", "jobs:write"]

    def test_an_unknown_permission_is_rejected(self):
        with pytest.raises(UnknownPermission, match="jobs:destroy"):
            validate_permissions(["jobs:destroy"])

    def test_the_catalogue_is_not_empty(self):
        assert "jobs:write" in ALL_PERMISSIONS
        assert "roles:manage" in ALL_PERMISSIONS


# --------------------------------------------------------------- flows

def seed_superadmin(fakes, email="super@example.com", password="super-secret"):
    user = {
        "_id": ObjectId(),
        "email": email,
        "name": "Super",
        "kind": "administration",
        "role": None,
        "is_superadmin": True,
        "active": True,
        "password_hash": hash_password(password),
    }
    fakes.users.documents.append(user)
    return user


def seed_admin(fakes, role, email="admin@example.com", password="admin-secret"):
    user = {
        "_id": ObjectId(),
        "email": email,
        "name": "Admin",
        "kind": "administration",
        "role": role,
        "is_superadmin": False,
        "active": True,
        "password_hash": hash_password(password),
    }
    fakes.users.documents.append(user)
    return user


def seed_role(fakes, name, permissions):
    role = {"_id": ObjectId(), "name": name, "permissions": permissions}
    fakes.roles.documents.append(role)
    return role


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def login(client, email, password):
    return await client.post(
        "/auth/login", json={"email": email, "password": password}
    )


@pytest.fixture
def real_auth(app_under_test):
    """Clear the superadmin overrides so the real guards run."""
    app_under_test.dependency_overrides.pop(auth_core.get_current_user, None)
    app_under_test.dependency_overrides.pop(auth_core.optional_user, None)
    return app_under_test


class TestLogin:
    async def test_correct_credentials_return_a_token(self, client, fakes, real_auth):
        seed_superadmin(fakes)

        response = await login(client, "super@example.com", "super-secret")

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["user"]["is_superadmin"] is True

    async def test_a_wrong_password_is_rejected(self, client, fakes, real_auth):
        seed_superadmin(fakes)

        response = await login(client, "super@example.com", "wrong")

        assert response.status_code == 401

    async def test_an_unknown_email_is_rejected_the_same_way(
        self, client, fakes, real_auth
    ):
        # Same message as a wrong password, so accounts are not enumerable.
        seed_superadmin(fakes)

        unknown = await login(client, "nobody@example.com", "whatever")
        wrong = await login(client, "super@example.com", "wrong")

        assert unknown.status_code == wrong.status_code == 401
        assert unknown.json()["detail"] == wrong.json()["detail"]

    async def test_a_disabled_account_cannot_sign_in(self, client, fakes, real_auth):
        user = seed_superadmin(fakes)
        user["active"] = False

        response = await login(client, "super@example.com", "super-secret")

        assert response.status_code == 401


class TestCandidateRegistration:
    async def test_self_signup_creates_a_candidate(self, client, fakes, real_auth):
        response = await client.post(
            "/auth/register",
            json={
                "email": "applicant@example.com",
                "password": "a-good-password",
                "name": "Applicant",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["user"]["kind"] == "candidate"
        assert body["user"]["is_superadmin"] is False
        assert body["user"]["permissions"] == []

    async def test_signup_cannot_grant_administration(
        self, client, fakes, real_auth
    ):
        """Even if extra fields are sent, registration only makes candidates."""
        await client.post(
            "/auth/register",
            json={
                "email": "sneaky@example.com",
                "password": "a-good-password",
                "name": "Sneaky",
                "kind": "administration",
                "is_superadmin": True,
            },
        )

        stored = fakes.users.documents[-1]
        assert stored["kind"] == "candidate"
        assert stored["is_superadmin"] is False

    async def test_a_duplicate_email_is_refused(self, client, fakes, real_auth):
        await client.post(
            "/auth/register",
            json={"email": "dup@example.com", "password": "a-good-password", "name": "A"},
        )

        again = await client.post(
            "/auth/register",
            json={"email": "dup@example.com", "password": "another-one", "name": "B"},
        )

        assert again.status_code == 409


class TestGuards:
    async def test_a_gated_route_rejects_an_anonymous_request(
        self, client, fakes, real_auth
    ):
        response = await client.get("/applications/")

        assert response.status_code == 401

    async def test_the_superadmin_reaches_a_gated_route(
        self, client, fakes, real_auth
    ):
        seed_superadmin(fakes)
        token = (await login(client, "super@example.com", "super-secret")).json()[
            "access_token"
        ]

        response = await client.get("/applications/", headers=auth(token))

        assert response.status_code == 200

    async def test_a_role_grants_exactly_its_permissions(
        self, client, fakes, real_auth
    ):
        seed_role(fakes, "viewer", ["candidates:read"])
        seed_admin(fakes, role="viewer")

        token = (await login(client, "admin@example.com", "admin-secret")).json()[
            "access_token"
        ]

        # viewer has candidates:read ...
        allowed = await client.get("/applications/", headers=auth(token))
        assert allowed.status_code == 200

        # ... but not jobs:write.
        denied = await client.post(
            "/jobs/",
            json={"title": "x", "description": "d"},
            headers=auth(token),
        )
        assert denied.status_code == 403
        assert "jobs:write" in denied.json()["detail"]

    async def test_editing_a_role_changes_access_immediately(
        self, client, fakes, real_auth
    ):
        """Permissions are resolved per request, not baked into the token."""
        role = seed_role(fakes, "viewer", ["candidates:read"])
        seed_admin(fakes, role="viewer")

        token = (await login(client, "admin@example.com", "admin-secret")).json()[
            "access_token"
        ]

        assert (
            await client.post(
                "/jobs/", json={"title": "x", "description": "d"}, headers=auth(token)
            )
        ).status_code == 403

        # Grant it without re-issuing the token.
        role["permissions"].append("jobs:write")

        assert (
            await client.post(
                "/jobs/", json={"title": "x", "description": "d"}, headers=auth(token)
            )
        ).status_code == 200

    async def test_a_candidate_cannot_reach_administration_routes(
        self, client, fakes, real_auth
    ):
        token = (
            await client.post(
                "/auth/register",
                json={
                    "email": "cand@example.com",
                    "password": "a-good-password",
                    "name": "Cand",
                },
            )
        ).json()["access_token"]

        response = await client.get("/applications/", headers=auth(token))

        assert response.status_code == 403

    async def test_me_returns_the_signed_in_user(self, client, fakes, real_auth):
        seed_superadmin(fakes)
        token = (await login(client, "super@example.com", "super-secret")).json()[
            "access_token"
        ]

        response = await client.get("/auth/me", headers=auth(token))

        assert response.status_code == 200
        assert response.json()["email"] == "super@example.com"

    async def test_a_token_for_a_deleted_user_is_worthless(
        self, client, fakes, real_auth
    ):
        user = seed_superadmin(fakes)
        token = (await login(client, "super@example.com", "super-secret")).json()[
            "access_token"
        ]

        fakes.users.documents.remove(user)

        response = await client.get("/auth/me", headers=auth(token))

        assert response.status_code == 401


class TestPublicSurfaceStaysOpen:
    """Candidates apply and interview without an account; that must not break."""

    async def test_applying_needs_no_auth(self, client, fakes, real_auth):
        job_id = ObjectId()
        fakes.jobs.documents.append(
            {"_id": job_id, "title": "Open", "description": "d", "status": "published"}
        )

        response = await client.post(
            "/applications/",
            data={"job_id": str(job_id)},
            files={"resume": ("cv.pdf", b"%PDF-1.4 x", "application/pdf")},
        )

        assert response.status_code == 200

    async def test_opening_an_invite_needs_no_auth(self, client, fakes, real_auth):
        token = ObjectId()
        fakes.sessions.documents.append(
            {
                "_id": ObjectId(),
                "candidate_id": str(ObjectId()),
                "job_id": str(ObjectId()),
                "questions": [],
                "current_question_index": 0,
                "total_time_seconds": 0,
                "status": "invited",
                "invite_token": "abc",
                "invite_expires_at": None,
                "intro_acknowledged_at": None,
            }
        )

        response = await client.get("/interviews/invite/abc")

        assert response.status_code == 200


class TestRoleManagement:
    async def test_superadmin_creates_a_role_with_permissions(
        self, client, fakes, real_auth
    ):
        seed_superadmin(fakes)
        token = (await login(client, "super@example.com", "super-secret")).json()[
            "access_token"
        ]

        response = await client.post(
            "/auth/roles",
            json={
                "name": "interviewer",
                "description": "Runs interviews",
                "permissions": ["interviews:read", "interviews:score"],
            },
            headers=auth(token),
        )

        assert response.status_code == 200
        assert response.json()["permissions"] == [
            "interviews:read",
            "interviews:score",
        ]

    async def test_an_unknown_permission_is_refused(self, client, fakes, real_auth):
        seed_superadmin(fakes)
        token = (await login(client, "super@example.com", "super-secret")).json()[
            "access_token"
        ]

        response = await client.post(
            "/auth/roles",
            json={"name": "bad", "permissions": ["jobs:obliterate"]},
            headers=auth(token),
        )

        assert response.status_code == 400

    async def test_an_admin_without_roles_manage_cannot_create_roles(
        self, client, fakes, real_auth
    ):
        seed_role(fakes, "recruiter", ["jobs:write", "candidates:read"])
        seed_admin(fakes, role="recruiter")

        token = (await login(client, "admin@example.com", "admin-secret")).json()[
            "access_token"
        ]

        response = await client.post(
            "/auth/roles",
            json={"name": "x", "permissions": []},
            headers=auth(token),
        )

        assert response.status_code == 403

    async def test_a_role_in_use_cannot_be_deleted(self, client, fakes, real_auth):
        seed_superadmin(fakes)
        seed_role(fakes, "recruiter", ["jobs:write"])
        seed_admin(fakes, role="recruiter")

        token = (await login(client, "super@example.com", "super-secret")).json()[
            "access_token"
        ]

        response = await client.delete("/auth/roles/recruiter", headers=auth(token))

        assert response.status_code == 409


class TestUserManagement:
    async def test_superadmin_creates_an_administration_user(
        self, client, fakes, real_auth
    ):
        seed_superadmin(fakes)
        seed_role(fakes, "recruiter", ["jobs:write"])

        token = (await login(client, "super@example.com", "super-secret")).json()[
            "access_token"
        ]

        response = await client.post(
            "/auth/users",
            json={
                "email": "newadmin@example.com",
                "password": "a-good-password",
                "name": "New Admin",
                "role": "recruiter",
                "kind": "administration",
            },
            headers=auth(token),
        )

        assert response.status_code == 200
        assert response.json()["role"] == "recruiter"
        assert response.json()["permissions"] == ["jobs:write"]

    async def test_creating_a_user_with_an_unknown_role_is_refused(
        self, client, fakes, real_auth
    ):
        seed_superadmin(fakes)
        token = (await login(client, "super@example.com", "super-secret")).json()[
            "access_token"
        ]

        response = await client.post(
            "/auth/users",
            json={
                "email": "x@example.com",
                "password": "a-good-password",
                "name": "X",
                "role": "nonexistent",
            },
            headers=auth(token),
        )

        assert response.status_code == 400

    async def test_disabling_a_user_blocks_their_next_sign_in(
        self, client, fakes, real_auth
    ):
        seed_superadmin(fakes)
        role = seed_role(fakes, "recruiter", ["jobs:write"])  # noqa: F841
        target = seed_admin(fakes, role="recruiter")

        token = (await login(client, "super@example.com", "super-secret")).json()[
            "access_token"
        ]

        response = await client.patch(
            f"/auth/users/{target['_id']}",
            json={"active": False},
            headers=auth(token),
        )

        assert response.status_code == 200
        assert target["active"] is False

    async def test_the_superadmin_account_cannot_be_modified(
        self, client, fakes, real_auth
    ):
        boss = seed_superadmin(fakes)
        token = (await login(client, "super@example.com", "super-secret")).json()[
            "access_token"
        ]

        response = await client.patch(
            f"/auth/users/{boss['_id']}",
            json={"active": False},
            headers=auth(token),
        )

        assert response.status_code == 403


class TestJobVisibility:
    """Drafts and closed roles are only visible to a jobs:read holder.

    The candidate portal and anonymous visitors must see open roles and nothing
    more - a draft must not leak through the unfiltered list or by guessing its
    id. Regression: GET /jobs/ and GET /jobs/{id} were unauthenticated and
    returned every job.
    """

    def _seed_jobs(self, fakes):
        open_job = {"_id": ObjectId(), "title": "Open role", "status": "published"}
        draft_job = {"_id": ObjectId(), "title": "Secret draft", "status": "draft"}
        fakes.jobs.documents.append(open_job)
        fakes.jobs.documents.append(draft_job)
        return open_job, draft_job

    async def test_anonymous_sees_only_open_roles(self, client, fakes, real_auth):
        self._seed_jobs(fakes)

        body = (await client.get("/jobs/")).json()

        titles = {job["title"] for job in body}
        assert titles == {"Open role"}

    async def test_a_candidate_sees_only_open_roles(self, client, fakes, real_auth):
        self._seed_jobs(fakes)
        token = (
            await client.post(
                "/auth/register",
                json={
                    "email": "cand@example.com",
                    "password": "a-good-password",
                    "name": "Cand",
                },
            )
        ).json()["access_token"]

        body = (await client.get("/jobs/", headers=auth(token))).json()

        assert {job["title"] for job in body} == {"Open role"}

    async def test_a_jobs_reader_sees_drafts_too(self, client, fakes, real_auth):
        self._seed_jobs(fakes)
        seed_role(fakes, "viewer", ["jobs:read"])
        seed_admin(fakes, role="viewer")
        token = (await login(client, "admin@example.com", "admin-secret")).json()[
            "access_token"
        ]

        body = (await client.get("/jobs/", headers=auth(token))).json()

        assert {job["title"] for job in body} == {"Open role", "Secret draft"}

    async def test_anonymous_cannot_open_a_draft_by_id(
        self, client, fakes, real_auth
    ):
        _, draft = self._seed_jobs(fakes)

        # A draft is indistinguishable from a missing one, so ids cannot be
        # probed to discover unpublished roles.
        response = await client.get(f"/jobs/{draft['_id']}")

        assert response.status_code == 404

    async def test_a_jobs_reader_can_open_a_draft_by_id(
        self, client, fakes, real_auth
    ):
        _, draft = self._seed_jobs(fakes)
        seed_role(fakes, "viewer", ["jobs:read"])
        seed_admin(fakes, role="viewer")
        token = (await login(client, "admin@example.com", "admin-secret")).json()[
            "access_token"
        ]

        response = await client.get(
            f"/jobs/{draft['_id']}", headers=auth(token)
        )

        assert response.status_code == 200
        assert response.json()["title"] == "Secret draft"


class TestRoleListingPermission:
    """Listing roles is allowed for either role or user managers; editing is
    roles:manage only."""

    async def test_a_user_manager_can_list_roles(self, client, fakes, real_auth):
        seed_role(fakes, "user_admin", ["users:manage"])
        seed_role(fakes, "recruiter", ["jobs:write"])
        seed_admin(fakes, role="user_admin")
        token = (await login(client, "admin@example.com", "admin-secret")).json()[
            "access_token"
        ]

        response = await client.get("/auth/roles", headers=auth(token))

        assert response.status_code == 200
        assert {r["name"] for r in response.json()} == {"user_admin", "recruiter"}

    async def test_a_user_manager_still_cannot_create_a_role(
        self, client, fakes, real_auth
    ):
        seed_role(fakes, "user_admin", ["users:manage"])
        seed_admin(fakes, role="user_admin")
        token = (await login(client, "admin@example.com", "admin-secret")).json()[
            "access_token"
        ]

        response = await client.post(
            "/auth/roles",
            json={"name": "x", "permissions": []},
            headers=auth(token),
        )

        assert response.status_code == 403

    async def test_without_either_permission_listing_is_denied(
        self, client, fakes, real_auth
    ):
        seed_role(fakes, "viewer", ["jobs:read"])
        seed_admin(fakes, role="viewer")
        token = (await login(client, "admin@example.com", "admin-secret")).json()[
            "access_token"
        ]

        response = await client.get("/auth/roles", headers=auth(token))

        assert response.status_code == 403

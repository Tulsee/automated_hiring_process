"""Tests for a job's application window.

A job is open only when its status, its publish date, its deadline and the
clock all agree. The state is derived rather than stored, so a deadline takes
effect the moment it passes with nothing scheduled to make it happen - these
tests pin that down, including for the jobs that existed before any of these
fields did.
"""

from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

from app.services.job_lifecycle import (
    STATE_CLOSED,
    STATE_DRAFT,
    STATE_EXPIRED,
    STATE_OPEN,
    STATE_SCHEDULED,
    ScheduleError,
    closed_reason,
    is_open,
    job_state,
    to_naive_utc,
    validate_schedule,
)

NOW = datetime(2026, 10, 16, 12, 0)
HOUR = timedelta(hours=1)
DAY = timedelta(days=1)


class TestDerivedState:
    def test_a_job_from_before_these_fields_existed_is_open(self):
        """The 16 jobs already in the database carry no status at all."""
        assert job_state({}, NOW) == STATE_OPEN
        assert is_open({}, NOW)

    def test_a_draft_is_never_visible(self):
        assert job_state({"status": "draft"}, NOW) == STATE_DRAFT

    def test_a_draft_stays_a_draft_even_inside_a_live_window(self):
        # The dates say open; the intent says not yet. Intent wins.
        job = {
            "status": "draft",
            "publish_at": NOW - DAY,
            "deadline": NOW + DAY,
        }

        assert job_state(job, NOW) == STATE_DRAFT

    def test_published_with_no_dates_is_open(self):
        assert job_state({"status": "published"}, NOW) == STATE_OPEN

    def test_a_future_publish_date_is_scheduled(self):
        job = {"status": "published", "publish_at": NOW + DAY}

        assert job_state(job, NOW) == STATE_SCHEDULED
        assert not is_open(job, NOW)

    def test_it_opens_once_the_publish_date_passes(self):
        job = {"status": "published", "publish_at": NOW + HOUR}

        assert job_state(job, NOW) == STATE_SCHEDULED
        # Nothing ran in between; only the clock moved.
        assert job_state(job, NOW + 2 * HOUR) == STATE_OPEN

    def test_a_passed_deadline_expires_it(self):
        job = {"status": "published", "deadline": NOW - HOUR}

        assert job_state(job, NOW) == STATE_EXPIRED
        assert not is_open(job, NOW)

    def test_it_closes_the_moment_the_deadline_passes(self):
        job = {"status": "published", "deadline": NOW + HOUR}

        assert job_state(job, NOW) == STATE_OPEN
        assert job_state(job, NOW + 2 * HOUR) == STATE_EXPIRED

    def test_a_deadline_exactly_now_is_still_open(self):
        # The deadline is the last moment, not the first closed one.
        job = {"status": "published", "deadline": NOW}

        assert job_state(job, NOW) == STATE_OPEN

    def test_closing_by_hand_beats_a_future_deadline(self):
        job = {"status": "closed", "deadline": NOW + DAY}

        assert job_state(job, NOW) == STATE_CLOSED

    def test_a_full_window_is_open_in_the_middle(self):
        job = {
            "status": "published",
            "publish_at": NOW - DAY,
            "deadline": NOW + DAY,
        }

        assert job_state(job, NOW) == STATE_OPEN


class TestTimezones:
    def test_an_offset_deadline_is_compared_correctly(self):
        """A client may send any offset; the stored clock is naive UTC."""
        kathmandu = timezone(timedelta(hours=5, minutes=45))

        # 17:00 +05:45 is 11:15 UTC, which is before NOW.
        job = {
            "status": "published",
            "deadline": datetime(2026, 10, 16, 17, 0, tzinfo=kathmandu),
        }

        assert job_state(job, NOW) == STATE_EXPIRED

    def test_normalisation_converts_rather_than_truncates(self):
        kathmandu = timezone(timedelta(hours=5, minutes=45))

        converted = to_naive_utc(datetime(2026, 11, 1, 12, 0, tzinfo=kathmandu))

        assert converted == datetime(2026, 11, 1, 6, 15)

    def test_a_naive_datetime_is_left_alone(self):
        assert to_naive_utc(NOW) == NOW

    def test_none_stays_none(self):
        assert to_naive_utc(None) is None


class TestClosedReason:
    def test_an_open_role_has_nothing_to_explain(self):
        assert closed_reason({"status": "published"}, NOW) == "This role is open."

    def test_a_draft_says_it_is_unpublished(self):
        assert "not published" in closed_reason({"status": "draft"}, NOW)

    def test_a_scheduled_role_says_when_it_opens(self):
        reason = closed_reason(
            {"status": "published", "publish_at": datetime(2026, 11, 1, 9, 0)},
            NOW,
        )

        assert "01 Nov 2026 09:00" in reason

    def test_an_expired_role_says_when_it_closed(self):
        reason = closed_reason(
            {"status": "published", "deadline": datetime(2026, 10, 1, 23, 59)},
            NOW,
        )

        assert "01 Oct 2026 23:59" in reason


class TestScheduleValidation:
    def test_a_deadline_after_publishing_is_fine(self):
        validate_schedule(NOW, NOW + DAY)

    def test_either_date_alone_is_fine(self):
        validate_schedule(NOW, None)
        validate_schedule(None, NOW)
        validate_schedule(None, None)

    def test_a_deadline_before_publishing_is_rejected(self):
        with pytest.raises(ScheduleError, match="after the publish date"):
            validate_schedule(NOW + DAY, NOW)

    def test_a_deadline_equal_to_publishing_is_rejected(self):
        # It would open and close in the same instant.
        with pytest.raises(ScheduleError):
            validate_schedule(NOW, NOW)


class TestCreateWithWindow:
    async def test_creates_a_published_role_by_default(self, client):
        response = await client.post(
            "/jobs/",
            json={"title": "Backend Engineer", "description": "d"},
        )

        assert response.status_code == 200
        body = response.json()

        assert body["status"] == "published"
        assert body["state"] == "open"
        assert body["state_reason"] is None

    async def test_creates_a_draft(self, client):
        response = await client.post(
            "/jobs/",
            json={"title": "Secret role", "description": "d", "status": "draft"},
        )

        body = response.json()

        assert body["state"] == "draft"
        assert "not published" in body["state_reason"]

    async def test_schedules_a_future_publication(self, client):
        response = await client.post(
            "/jobs/",
            json={
                "title": "Opens later",
                "description": "d",
                "publish_at": "2099-01-01T09:00:00",
            },
        )

        body = response.json()

        assert body["state"] == "scheduled"
        assert "opens for applications on" in body["state_reason"]

    async def test_rejects_an_impossible_window(self, client):
        response = await client.post(
            "/jobs/",
            json={
                "title": "Nonsense",
                "description": "d",
                "publish_at": "2099-02-01T09:00:00",
                "deadline": "2099-01-01T09:00:00",
            },
        )

        assert response.status_code == 400
        assert "after the publish date" in response.json()["detail"]

    async def test_rejects_an_unknown_status(self, client):
        response = await client.post(
            "/jobs/",
            json={"title": "x", "description": "d", "status": "whenever"},
        )

        assert response.status_code == 400


class TestUpdate:
    async def test_changes_the_description(self, client, fakes):
        created = (
            await client.post("/jobs/", json={"title": "x", "description": "old"})
        ).json()

        response = await client.patch(
            f"/jobs/{created['id']}", json={"description": "new"}
        )

        assert response.status_code == 200
        assert response.json()["description"] == "new"

    async def test_changes_the_required_skills(self, client):
        created = (
            await client.post("/jobs/", json={"title": "x", "description": "d"})
        ).json()

        response = await client.patch(
            f"/jobs/{created['id']}",
            json={"required_skills": ["python", "rust"]},
        )

        assert response.json()["required_skills"] == ["python", "rust"]

    async def test_replaces_the_interview_questions(self, client):
        created = (
            await client.post(
                "/jobs/",
                json={
                    "title": "x",
                    "description": "d",
                    "interview_questions": [{"text": "old question"}],
                },
            )
        ).json()

        response = await client.patch(
            f"/jobs/{created['id']}",
            json={
                "interview_questions": [
                    {
                        "text": "new question",
                        "competency": "system_design",
                        "time_limit_seconds": 120,
                    }
                ]
            },
        )

        questions = response.json()["interview_questions"]

        assert len(questions) == 1
        assert questions[0]["text"] == "new question"
        assert questions[0]["time_limit_seconds"] == 120

    async def test_sets_a_deadline(self, client):
        created = (
            await client.post("/jobs/", json={"title": "x", "description": "d"})
        ).json()

        response = await client.patch(
            f"/jobs/{created['id']}", json={"deadline": "2099-12-01T23:59:00"}
        )

        assert response.json()["state"] == "open"
        assert response.json()["deadline"].startswith("2099-12-01")

    async def test_a_past_deadline_closes_the_role_immediately(self, client):
        created = (
            await client.post("/jobs/", json={"title": "x", "description": "d"})
        ).json()

        response = await client.patch(
            f"/jobs/{created['id']}", json={"deadline": "2020-01-01T00:00:00"}
        )

        # Nothing was scheduled; the state simply follows the clock.
        assert response.json()["state"] == "expired"
        assert "closed on 01 Jan 2020" in response.json()["state_reason"]

    async def test_clears_a_deadline_with_an_explicit_null(self, client):
        created = (
            await client.post(
                "/jobs/",
                json={
                    "title": "x",
                    "description": "d",
                    "deadline": "2020-01-01T00:00:00",
                },
            )
        ).json()

        assert created["state"] == "expired"

        response = await client.patch(
            f"/jobs/{created['id']}", json={"deadline": None}
        )

        assert response.json()["deadline"] is None
        assert response.json()["state"] == "open"

    async def test_leaves_untouched_fields_alone(self, client):
        created = (
            await client.post(
                "/jobs/",
                json={
                    "title": "Keep me",
                    "description": "d",
                    "required_skills": ["python"],
                    "interview_questions": [{"text": "keep this"}],
                },
            )
        ).json()

        response = await client.patch(
            f"/jobs/{created['id']}", json={"description": "changed"}
        )

        body = response.json()

        assert body["title"] == "Keep me"
        assert body["required_skills"] == ["python"]
        assert body["interview_questions"][0]["text"] == "keep this"

    async def test_publishes_a_draft(self, client):
        created = (
            await client.post(
                "/jobs/",
                json={"title": "x", "description": "d", "status": "draft"},
            )
        ).json()

        response = await client.patch(
            f"/jobs/{created['id']}", json={"status": "published"}
        )

        assert response.json()["state"] == "open"

    async def test_closes_a_role_by_hand(self, client):
        created = (
            await client.post("/jobs/", json={"title": "x", "description": "d"})
        ).json()

        response = await client.patch(
            f"/jobs/{created['id']}", json={"status": "closed"}
        )

        assert response.json()["state"] == "closed"

    async def test_validates_the_window_after_the_change_not_just_the_request(
        self, client
    ):
        """Sending only a deadline must still be checked against the stored
        publish date."""
        created = (
            await client.post(
                "/jobs/",
                json={
                    "title": "x",
                    "description": "d",
                    "publish_at": "2099-06-01T09:00:00",
                },
            )
        ).json()

        response = await client.patch(
            f"/jobs/{created['id']}", json={"deadline": "2099-01-01T09:00:00"}
        )

        assert response.status_code == 400
        assert "after the publish date" in response.json()["detail"]

    async def test_rejects_an_empty_update(self, client):
        created = (
            await client.post("/jobs/", json={"title": "x", "description": "d"})
        ).json()

        response = await client.patch(f"/jobs/{created['id']}", json={})

        assert response.status_code == 400

    async def test_rejects_an_unknown_job(self, client):
        response = await client.patch(
            f"/jobs/{ObjectId()}", json={"description": "x"}
        )

        assert response.status_code == 404

    async def test_rejects_a_malformed_id(self, client):
        response = await client.patch("/jobs/nope", json={"description": "x"})

        assert response.status_code == 400


class TestListing:
    async def seed(self, client):
        await client.post(
            "/jobs/", json={"title": "Open role", "description": "d"}
        )
        await client.post(
            "/jobs/",
            json={"title": "Draft role", "description": "d", "status": "draft"},
        )
        await client.post(
            "/jobs/",
            json={
                "title": "Expired role",
                "description": "d",
                "deadline": "2020-01-01T00:00:00",
            },
        )
        await client.post(
            "/jobs/",
            json={
                "title": "Future role",
                "description": "d",
                "publish_at": "2099-01-01T00:00:00",
            },
        )

    async def test_a_recruiter_sees_everything_by_default(self, client):
        await self.seed(client)

        body = (await client.get("/jobs/")).json()

        assert {job["title"] for job in body} == {
            "Open role",
            "Draft role",
            "Expired role",
            "Future role",
        }

    async def test_open_only_hides_drafts_expired_and_scheduled(self, client):
        """What the candidate portal asks for: a deadline that has passed must
        take the role off the list."""
        await self.seed(client)

        body = (await client.get("/jobs/?open_only=true")).json()

        assert [job["title"] for job in body] == ["Open role"]

    async def test_filters_by_status(self, client):
        await self.seed(client)

        body = (await client.get("/jobs/?status=draft")).json()

        assert [job["title"] for job in body] == ["Draft role"]

    async def test_every_row_carries_its_state(self, client):
        await self.seed(client)

        body = (await client.get("/jobs/")).json()

        states = {job["title"]: job["state"] for job in body}

        assert states == {
            "Open role": "open",
            "Draft role": "draft",
            "Expired role": "expired",
            "Future role": "scheduled",
        }


class TestGetOne:
    async def test_returns_a_job_with_its_state(self, client):
        created = (
            await client.post("/jobs/", json={"title": "x", "description": "d"})
        ).json()

        response = await client.get(f"/jobs/{created['id']}")

        assert response.status_code == 200
        assert response.json()["state"] == "open"

    async def test_rejects_an_unknown_job(self, client):
        assert (await client.get(f"/jobs/{ObjectId()}")).status_code == 404

    async def test_rejects_a_malformed_id(self, client):
        assert (await client.get("/jobs/nope")).status_code == 400


class TestApplyingIsGated:
    """A closed role must refuse applications, not just hide itself.

    Hiding it from the listing is not enough: an applicant may still hold the
    link, and the portal's copy of the list may be minutes old.
    """

    async def apply_to(self, client, job_id):
        return await client.post(
            "/applications/",
            data={"job_id": job_id},
            files={"resume": ("cv.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )

    async def test_an_open_role_accepts_an_application(self, client, fakes):
        created = (
            await client.post("/jobs/", json={"title": "x", "description": "d"})
        ).json()

        response = await self.apply_to(client, created["id"])

        assert response.status_code == 200
        assert len(fakes.candidates.documents) == 1

    async def test_a_passed_deadline_refuses_it(self, client, fakes):
        created = (
            await client.post(
                "/jobs/",
                json={
                    "title": "x",
                    "description": "d",
                    "deadline": "2020-01-01T00:00:00",
                },
            )
        ).json()

        response = await self.apply_to(client, created["id"])

        assert response.status_code == 409
        assert "closed on 01 Jan 2020" in response.json()["detail"]
        # Nothing was stored, so no resume sits on disk unreferenced either.
        assert fakes.candidates.documents == []

    async def test_a_draft_refuses_it(self, client, fakes):
        created = (
            await client.post(
                "/jobs/",
                json={"title": "x", "description": "d", "status": "draft"},
            )
        ).json()

        response = await self.apply_to(client, created["id"])

        assert response.status_code == 409
        assert "not published" in response.json()["detail"]
        assert fakes.candidates.documents == []

    async def test_a_scheduled_role_refuses_it_and_says_when_it_opens(
        self, client, fakes
    ):
        created = (
            await client.post(
                "/jobs/",
                json={
                    "title": "x",
                    "description": "d",
                    "publish_at": "2099-01-01T09:00:00",
                },
            )
        ).json()

        response = await self.apply_to(client, created["id"])

        assert response.status_code == 409
        assert "opens for applications on 01 Jan 2099" in response.json()["detail"]
        assert fakes.candidates.documents == []

    async def test_a_hand_closed_role_refuses_it(self, client, fakes):
        created = (
            await client.post("/jobs/", json={"title": "x", "description": "d"})
        ).json()

        await client.patch(f"/jobs/{created['id']}", json={"status": "closed"})

        response = await self.apply_to(client, created["id"])

        assert response.status_code == 409
        assert "no longer accepting" in response.json()["detail"]

    async def test_a_role_from_before_these_fields_existed_still_accepts(
        self, client, fakes
    ):
        """The jobs already in the database must not all start refusing."""
        job_id = ObjectId()

        fakes.jobs.documents.append(
            {
                "_id": job_id,
                "title": "Legacy role",
                "description": "d",
                "required_skills": [],
            }
        )

        response = await self.apply_to(client, str(job_id))

        assert response.status_code == 200

    async def test_moving_the_deadline_reopens_it(self, client, fakes):
        created = (
            await client.post(
                "/jobs/",
                json={
                    "title": "x",
                    "description": "d",
                    "deadline": "2020-01-01T00:00:00",
                },
            )
        ).json()

        assert (await self.apply_to(client, created["id"])).status_code == 409

        await client.patch(
            f"/jobs/{created['id']}", json={"deadline": "2099-01-01T00:00:00"}
        )

        assert (await self.apply_to(client, created["id"])).status_code == 200

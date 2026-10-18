"""The candidate's own application-tracking view."""

from datetime import datetime

from bson import ObjectId

from app.services.application_journey import (
    CURRENT,
    DONE,
    PENDING,
    SKIPPED,
    application_journey,
    journey_summary,
)


def step(steps, key):
    return next(s for s in steps if s["key"] == key)


class TestJourney:
    def test_a_fresh_application_is_applied_and_screening(self):
        steps = application_journey({"status": "received"})

        assert step(steps, "applied")["state"] == DONE
        assert step(steps, "screening")["state"] == CURRENT
        assert step(steps, "decision")["state"] == PENDING

    def test_a_scored_but_undecided_application_awaits_a_decision(self):
        steps = application_journey(
            {"status": "processed", "screening_score": 72.0}
        )

        assert step(steps, "screening")["state"] == DONE
        assert step(steps, "decision")["state"] == PENDING

    def test_a_rejected_application_skips_the_interview_track(self):
        steps = application_journey(
            {"status": "processed", "screening_score": 40.0, "decision": "reject"}
        )

        assert step(steps, "decision")["state"] == DONE
        assert step(steps, "interview")["state"] == SKIPPED
        assert step(steps, "assessment")["state"] == SKIPPED
        # A rejected application has reached its outcome.
        assert step(steps, "outcome")["state"] == DONE

    def test_an_invited_application_shows_the_interview_as_current(self):
        steps = application_journey(
            {"status": "processed", "decision": "invited_to_interview"},
            session={"status": "invited", "answered_count": 0, "total_questions": 3},
        )

        assert step(steps, "decision")["state"] == DONE
        assert step(steps, "interview")["state"] == CURRENT
        assert "invite" in step(steps, "interview")["detail"].lower()

    def test_interview_in_progress_reports_answered_count(self):
        steps = application_journey(
            {"status": "processed", "decision": "invited_to_interview"},
            session={
                "status": "in_progress",
                "answered_count": 1,
                "total_questions": 3,
            },
        )

        assert "1 of 3" in step(steps, "interview")["detail"]

    def test_a_submitted_interview_is_done_and_assessment_current(self):
        steps = application_journey(
            {"status": "processed", "decision": "invited_to_interview"},
            session={"status": "submitted", "scoring_status": None},
        )

        assert step(steps, "interview")["state"] == DONE
        assert step(steps, "assessment")["state"] == CURRENT

    def test_a_scored_interview_completes_assessment(self):
        steps = application_journey(
            {"status": "processed", "decision": "invited_to_interview"},
            session={"status": "submitted", "scoring_status": "completed"},
        )

        assert step(steps, "assessment")["state"] == DONE
        # The final outcome is still a human call.
        assert step(steps, "outcome")["state"] == PENDING

    def test_a_parsing_error_surfaces_as_a_manual_review(self):
        steps = application_journey({"status": "error"})

        assert step(steps, "screening")["state"] == CURRENT
        assert "by hand" in step(steps, "screening")["detail"]

    def test_the_older_decision_spelling_counts_as_invited(self):
        steps = application_journey(
            {"status": "processed", "decision": "invite_to_interview"},
            session={"status": "invited"},
        )

        assert step(steps, "interview")["state"] != SKIPPED


class TestSummary:
    def test_current_is_the_first_unfinished_step(self):
        summary = journey_summary({"status": "received"})

        assert summary["current"]["key"] == "screening"

    def test_completed_counts_done_steps(self):
        summary = journey_summary(
            {"status": "processed", "decision": "invited_to_interview"},
            session={"status": "submitted", "scoring_status": "completed"},
        )

        # applied, screening, decision, interview, assessment done; outcome pending
        assert summary["completed"] == 5
        assert summary["total"] == 6

    def test_skipped_steps_are_excluded_from_the_total(self):
        summary = journey_summary(
            {"status": "processed", "decision": "reject"}
        )

        # applied, screening, decision, outcome — interview/assessment skipped
        assert summary["total"] == 4


class TestMineEndpoint:
    """GET /applications/mine, scoped to the signed-in user."""

    def seed_me(self, principal, email="me@example.com"):
        # /mine matches on the caller's id/email, so align the fixture
        # principal (the account `client` is signed in as) to our data.
        principal["email"] = email
        return principal

    async def test_lists_only_my_applications(self, client, fakes, principal):
        me = self.seed_me(principal)
        job = {"_id": ObjectId(), "title": "Backend Engineer"}
        fakes.jobs.documents.append(job)

        # mine, by user id
        fakes.candidates.documents.append(
            {
                "_id": ObjectId(),
                "job_id": str(job["_id"]),
                "applicant_user_id": str(me["_id"]),
                "applicant_email": me["email"],
                "status": "received",
                "created_at": datetime.utcnow(),
            }
        )
        # someone else's
        fakes.candidates.documents.append(
            {
                "_id": ObjectId(),
                "job_id": str(job["_id"]),
                "applicant_user_id": str(ObjectId()),
                "applicant_email": "other@example.com",
                "status": "received",
                "created_at": datetime.utcnow(),
            }
        )

        body = (await client.get("/applications/mine")).json()

        assert body["total"] == 1
        assert body["applications"][0]["job_title"] == "Backend Engineer"

    async def test_matches_by_email_when_applied_before_signing_up(
        self, client, fakes, principal
    ):
        me = self.seed_me(principal, email="early@example.com")
        job = {"_id": ObjectId(), "title": "Data Engineer"}
        fakes.jobs.documents.append(job)

        # Applied anonymously; only the extracted resume email links it.
        fakes.candidates.documents.append(
            {
                "_id": ObjectId(),
                "job_id": str(job["_id"]),
                "applicant_user_id": None,
                "email": "early@example.com",
                "status": "processed",
                "screening_score": 70.0,
                "created_at": datetime.utcnow(),
            }
        )

        body = (await client.get("/applications/mine")).json()

        assert body["total"] == 1

    async def test_reports_the_current_step_and_progress(
        self, client, fakes, principal
    ):
        me = self.seed_me(principal, email="step@example.com")
        job = {"_id": ObjectId(), "title": "Backend Engineer"}
        fakes.jobs.documents.append(job)

        candidate_id = ObjectId()
        fakes.candidates.documents.append(
            {
                "_id": candidate_id,
                "job_id": str(job["_id"]),
                "applicant_user_id": str(me["_id"]),
                "status": "processed",
                "decision": "invited_to_interview",
                "interview_invite_url": "http://x/interview?token=abc",
                "created_at": datetime.utcnow(),
            }
        )
        fakes.sessions.documents.append(
            {
                "_id": ObjectId(),
                "candidate_id": str(candidate_id),
                "questions": [{"id": "q1"}, {"id": "q2"}, {"id": "q3"}],
                "status": "invited",
            }
        )

        app = (await client.get("/applications/mine")).json()["applications"][0]

        assert app["current_step"]["key"] == "interview"
        assert app["interview_invite_url"].endswith("token=abc")
        assert app["interview_status"] == "invited"
        assert app["total_steps"] == 6
        assert len(app["steps"]) == 6

    async def test_no_applications_is_an_empty_list(self, client, fakes, principal):
        self.seed_me(principal, email="nobody@example.com")

        body = (await client.get("/applications/mine")).json()

        assert body == {"total": 0, "applications": []}

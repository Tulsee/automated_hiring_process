"""Tests for Module 11: per-job questions, competencies, invites, intro.

Covers the interview template (fixed ordered questions per job, each tagged
with the competency it tests), the unique expiring invite link, and the intro
screen the candidate must acknowledge before recording.
"""

from datetime import datetime, timedelta

import pytest
from bson import ObjectId

from app.services.interview_questions import (
    DEFAULT_INTERVIEW_QUESTIONS,
    get_questions_for_job,
)
from app.services.interview_service import (
    DECISION_INVITED_TO_INTERVIEW,
    ELIGIBLE_DECISIONS,
    build_invite_url,
)


async def create_session(client, candidate_id):
    return await client.post(
        "/interviews/sessions", json={"candidate_id": str(candidate_id)}
    )


def add_candidate(fakes, job_id, decision=DECISION_INVITED_TO_INTERVIEW):
    candidate = {
        "_id": ObjectId(),
        "job_id": job_id,
        "decision": decision,
    }
    fakes.candidates.documents.append(candidate)
    return candidate


class TestCompetencyTags:
    def test_every_default_question_declares_a_competency(self):
        competencies = [
            question["competency"] for question in DEFAULT_INTERVIEW_QUESTIONS
        ]

        assert competencies == [
            "technical_depth",
            "system_design",
            "problem_solving",
        ]

    def test_default_questions_keep_their_order_and_time_limits(self):
        questions = get_questions_for_job(None)

        assert [question["id"] for question in questions] == [
            "question_1",
            "question_2",
            "question_3",
        ]
        assert [question["time_limit_seconds"] for question in questions] == [
            60,
            90,
            120,
        ]

    async def test_session_response_exposes_the_competency(
        self, client, fakes
    ):
        candidate = add_candidate(fakes, str(ObjectId()))

        response = await create_session(client, candidate["_id"])

        competencies = [
            question["competency"] for question in response.json()["questions"]
        ]

        assert competencies == [
            "technical_depth",
            "system_design",
            "problem_solving",
        ]


class TestQuestionsPerJob:
    async def test_job_defined_questions_are_used(self, client, fakes):
        job_id = ObjectId()
        fakes.jobs.documents.append(
            {
                "_id": job_id,
                "title": "Data Engineer",
                "interview_questions": [
                    {
                        "id": "pipelines",
                        "text": "Walk us through a pipeline you built.",
                        "competency": "data_modelling",
                        "time_limit_seconds": 75,
                    },
                    {
                        "id": "quality",
                        "text": "How do you catch bad data?",
                        "competency": "data_quality",
                        "time_limit_seconds": 45,
                    },
                ],
            }
        )

        candidate = add_candidate(fakes, str(job_id))

        body = (await create_session(client, candidate["_id"])).json()

        assert body["total_questions"] == 2
        assert body["total_time_seconds"] == 120
        assert [question["id"] for question in body["questions"]] == [
            "pipelines",
            "quality",
        ]
        assert body["questions"][0]["competency"] == "data_modelling"

    async def test_two_jobs_get_different_question_sets(self, client, fakes):
        backend_job = ObjectId()
        design_job = ObjectId()

        fakes.jobs.documents.append({"_id": backend_job})
        fakes.jobs.documents.append(
            {
                "_id": design_job,
                "interview_questions": [
                    {"text": "Critique this layout.", "competency": "visual"}
                ],
            }
        )

        backend = add_candidate(fakes, str(backend_job))
        design = add_candidate(fakes, str(design_job))

        backend_body = (await create_session(client, backend["_id"])).json()
        design_body = (await create_session(client, design["_id"])).json()

        assert backend_body["total_questions"] == 3
        assert design_body["total_questions"] == 1
        assert design_body["questions"][0]["competency"] == "visual"

    def test_a_job_question_without_an_id_or_limit_is_filled_in(self):
        questions = get_questions_for_job(
            {"interview_questions": [{"text": "Why this role?"}]}
        )

        assert questions[0]["id"] == "question_1"
        assert questions[0]["competency"] == "general"
        assert questions[0]["time_limit_seconds"] == 90

    async def test_job_missing_from_the_database_falls_back_to_default(
        self, client, fakes
    ):
        candidate = add_candidate(fakes, str(ObjectId()))

        body = (await create_session(client, candidate["_id"])).json()

        assert body["total_questions"] == 3


class TestEligibility:
    async def test_both_decision_spellings_are_accepted(self, client, fakes):
        """The screening graph used to write `invite_to_interview`, so
        candidates in the database carry either spelling."""
        for decision in sorted(ELIGIBLE_DECISIONS):
            candidate = add_candidate(fakes, str(ObjectId()), decision=decision)

            response = await create_session(client, candidate["_id"])

            assert response.status_code == 200, decision

    async def test_graph_writes_the_spelling_the_route_accepts(self):
        """Regression: the two halves disagreed, so no screened candidate
        could ever start an interview."""
        from app.agent import graph

        assert DECISION_INVITED_TO_INTERVIEW in ELIGIBLE_DECISIONS
        assert graph.DECISION_INVITED_TO_INTERVIEW == DECISION_INVITED_TO_INTERVIEW

    async def test_other_decisions_are_still_rejected(self, client, fakes):
        candidate = add_candidate(fakes, str(ObjectId()), decision="reject")

        response = await create_session(client, candidate["_id"])

        assert response.status_code == 400


class TestInviteLink:
    async def test_session_creation_returns_a_unique_invite_link(
        self, client, fakes
    ):
        first = add_candidate(fakes, str(ObjectId()))
        second = add_candidate(fakes, str(ObjectId()))

        first_body = (await create_session(client, first["_id"])).json()
        second_body = (await create_session(client, second["_id"])).json()

        assert first_body["invite_token"]
        assert first_body["invite_token"] != second_body["invite_token"]
        assert first_body["invite_url"].endswith(first_body["invite_token"])
        assert "token=" in first_body["invite_url"]

    async def test_invite_carries_an_expiry(self, client, fakes):
        candidate = add_candidate(fakes, str(ObjectId()))

        body = (await create_session(client, candidate["_id"])).json()

        assert body["invite_expires_at"] is not None

        stored = fakes.sessions.documents[0]
        assert stored["invite_expires_at"] > datetime.utcnow()

    def test_invite_url_points_at_the_candidate_page(self):
        assert build_invite_url("abc123").endswith("/interview?token=abc123")

    async def test_the_invite_link_opens_the_session(self, client, fakes):
        candidate = add_candidate(fakes, str(ObjectId()))

        created = (await create_session(client, candidate["_id"])).json()

        response = await client.get(f"/interviews/invite/{created['invite_token']}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == created["id"]
        assert body["total_questions"] == 3
        assert body["intro_acknowledged"] is False

    async def test_an_unknown_token_is_rejected(self, client):
        response = await client.get("/interviews/invite/not-a-real-token")

        assert response.status_code == 404

    async def test_an_expired_invite_is_rejected(self, client, fakes):
        candidate = add_candidate(fakes, str(ObjectId()))

        created = (await create_session(client, candidate["_id"])).json()

        fakes.sessions.documents[0]["invite_expires_at"] = (
            datetime.utcnow() - timedelta(hours=1)
        )

        response = await client.get(f"/interviews/invite/{created['invite_token']}")

        assert response.status_code == 410
        assert "expired" in response.json()["detail"]

    async def test_an_expired_invite_cannot_be_acknowledged(
        self, client, fakes
    ):
        candidate = add_candidate(fakes, str(ObjectId()))

        created = (await create_session(client, candidate["_id"])).json()

        fakes.sessions.documents[0]["invite_expires_at"] = (
            datetime.utcnow() - timedelta(hours=1)
        )

        response = await client.post(
            f"/interviews/invite/{created['invite_token']}/acknowledge"
        )

        assert response.status_code == 410


class TestIntroAcknowledgement:
    async def test_acknowledging_unlocks_the_first_question(
        self, client, fakes
    ):
        candidate = add_candidate(fakes, str(ObjectId()))

        created = (await create_session(client, candidate["_id"])).json()

        response = await client.post(
            f"/interviews/invite/{created['invite_token']}/acknowledge"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "in_progress"
        assert body["intro_acknowledged"] is True
        assert body["question"]["id"] == "question_1"
        assert body["question"]["time_limit_seconds"] == 60

        stored = fakes.sessions.documents[0]
        assert isinstance(stored["intro_acknowledged_at"], datetime)

    async def test_recording_is_blocked_before_the_intro_is_accepted(
        self, client, fakes
    ):
        candidate = add_candidate(fakes, str(ObjectId()))

        created = (await create_session(client, candidate["_id"])).json()

        response = await client.post(
            "/interviews/answers",
            data={"session_id": created["id"], "question_id": "question_1"},
            files={"answer": ("a.webm", b"x" * 100, "video/webm")},
        )

        assert response.status_code == 403
        assert "intro" in response.json()["detail"].lower()
        assert len(fakes.answers.documents) == 0

    async def test_recording_is_allowed_after_the_intro_is_accepted(
        self, client, fakes
    ):
        candidate = add_candidate(fakes, str(ObjectId()))

        created = (await create_session(client, candidate["_id"])).json()

        await client.post(
            f"/interviews/invite/{created['invite_token']}/acknowledge"
        )

        response = await client.post(
            "/interviews/answers",
            data={"session_id": created["id"], "question_id": "question_1"},
            files={"answer": ("a.webm", b"x" * 100, "video/webm")},
        )

        assert response.status_code == 200

    async def test_acknowledging_twice_is_harmless(self, client, fakes):
        """Reloading the intro page must not reset progress."""
        candidate = add_candidate(fakes, str(ObjectId()))

        created = (await create_session(client, candidate["_id"])).json()

        token = created["invite_token"]

        first = await client.post(f"/interviews/invite/{token}/acknowledge")

        first_at = fakes.sessions.documents[0]["intro_acknowledged_at"]

        second = await client.post(f"/interviews/invite/{token}/acknowledge")

        assert first.status_code == 200
        assert second.status_code == 200
        assert fakes.sessions.documents[0]["intro_acknowledged_at"] == first_at

    async def test_reopening_the_link_mid_interview_resumes(
        self, client, fakes
    ):
        candidate = add_candidate(fakes, str(ObjectId()))

        created = (await create_session(client, candidate["_id"])).json()

        token = created["invite_token"]

        await client.post(f"/interviews/invite/{token}/acknowledge")

        await client.post(
            "/interviews/answers",
            data={"session_id": created["id"], "question_id": "question_1"},
            files={"answer": ("a.webm", b"x" * 100, "video/webm")},
        )

        response = await client.get(f"/interviews/invite/{token}")

        body = response.json()
        assert body["intro_acknowledged"] is True
        assert body["status"] == "in_progress"
        assert body["question"]["id"] == "question_2"


class TestSessionDiscoverability:
    """A session_id must be findable without reading the database."""

    async def test_creating_a_session_records_it_on_the_candidate(
        self, client, fakes
    ):
        """Regression: only the screening graph wrote this back, so sessions
        created through the API showed a null interview_session_id."""
        candidate = add_candidate(fakes, str(ObjectId()))

        created = (await create_session(client, candidate["_id"])).json()

        assert candidate["interview_session_id"] == created["id"]
        assert candidate["interview_invite_url"] == created["invite_url"]

    async def test_the_candidate_listing_exposes_the_session_id(
        self, client, fakes
    ):
        candidate = add_candidate(fakes, str(ObjectId()))

        created = (await create_session(client, candidate["_id"])).json()

        row = (await client.get("/applications/")).json()["candidates"][0]

        assert row["interview_session_id"] == created["id"]

    async def test_sessions_can_be_listed(self, client, fakes):
        first = add_candidate(fakes, str(ObjectId()))
        second = add_candidate(fakes, str(ObjectId()))

        created = (await create_session(client, first["_id"])).json()
        await create_session(client, second["_id"])

        response = await client.get("/interviews/sessions")

        assert response.status_code == 200
        body = response.json()

        assert body["total"] == 2
        assert created["id"] in [session["id"] for session in body["sessions"]]

    async def test_a_session_row_shows_pipeline_progress(self, client, fakes):
        job_id = ObjectId()
        fakes.jobs.documents.append({"_id": job_id, "title": "Backend Engineer"})

        candidate = add_candidate(fakes, str(job_id))
        candidate["name"] = "Ama"

        created = (await create_session(client, candidate["_id"])).json()

        row = (await client.get("/interviews/sessions")).json()["sessions"][0]

        assert row["id"] == created["id"]
        assert row["candidate_name"] == "Ama"
        assert row["job_title"] == "Backend Engineer"
        assert row["status"] == "invited"
        assert row["total_questions"] == 3
        assert row["answered_count"] == 0
        assert row["overall_score"] is None

    async def test_sessions_can_be_filtered_by_status(self, client, fakes):
        first = add_candidate(fakes, str(ObjectId()))
        second = add_candidate(fakes, str(ObjectId()))

        created = (await create_session(client, first["_id"])).json()
        await create_session(client, second["_id"])

        await client.post(
            f"/interviews/invite/{created['invite_token']}/acknowledge"
        )

        body = (
            await client.get("/interviews/sessions?status=in_progress")
        ).json()

        assert body["total"] == 1
        assert body["sessions"][0]["id"] == created["id"]

    async def test_sessions_can_be_filtered_by_candidate(self, client, fakes):
        wanted = add_candidate(fakes, str(ObjectId()))
        other = add_candidate(fakes, str(ObjectId()))

        created = (await create_session(client, wanted["_id"])).json()
        await create_session(client, other["_id"])

        body = (
            await client.get(
                f"/interviews/sessions?candidate_id={wanted['_id']}"
            )
        ).json()

        assert body["total"] == 1
        assert body["sessions"][0]["id"] == created["id"]

    async def test_the_listing_route_does_not_shadow_a_session_id(
        self, client, fakes
    ):
        """`/sessions` must not swallow `/sessions/{id}`."""
        candidate = add_candidate(fakes, str(ObjectId()))

        created = (await create_session(client, candidate["_id"])).json()

        response = await client.get(f"/interviews/sessions/{created['id']}")

        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

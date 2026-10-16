"""Tests for the interview session endpoints."""

from datetime import datetime

from bson import ObjectId

from app.models.interview_session import create_interview_session_document


def test_sessions_collection_is_configured():
    """The route imports this name at module load; a typo breaks startup."""
    from app.db import mongodb

    assert mongodb.interview_sessions_collection.name == "interview_sessions"


class TestCreateSession:
    async def test_creates_session_for_eligible_candidate(
        self, client, candidate, fakes
    ):
        response = await client.post(
            "/interviews/sessions",
            json={"candidate_id": str(candidate["_id"])},
        )

        assert response.status_code == 200
        body = response.json()

        assert body["candidate_id"] == str(candidate["_id"])
        assert body["job_id"] == candidate["job_id"]
        assert body["status"] == "invited"
        assert body["intro_acknowledged"] is False
        assert body["current_question_index"] == 0
        assert len(fakes.sessions.documents) == 1

    async def test_response_includes_the_full_question_list(
        self, client, candidate
    ):
        """Regression: `questions` was missing from the response schema, so
        Pydantic silently dropped it."""
        response = await client.post(
            "/interviews/sessions",
            json={"candidate_id": str(candidate["_id"])},
        )

        body = response.json()

        assert body["total_questions"] == 3
        assert len(body["questions"]) == 3
        assert [question["id"] for question in body["questions"]] == [
            "question_1",
            "question_2",
            "question_3",
        ]
        assert body["total_time_seconds"] == 270
        # No current question until the intro is acknowledged.
        assert body["question"] is None

    async def test_job_id_is_serialised_as_a_string(
        self, client, fakes
    ):
        """Regression: an ObjectId `job_id` failed the `str` schema field."""
        job_id = ObjectId()
        candidate_id = ObjectId()
        fakes.candidates.documents.append(
            {
                "_id": candidate_id,
                "job_id": job_id,
                "decision": "invited_to_interview",
            }
        )

        response = await client.post(
            "/interviews/sessions", json={"candidate_id": str(candidate_id)}
        )

        assert response.status_code == 200
        assert response.json()["job_id"] == str(job_id)

    async def test_rejects_malformed_candidate_id(self, client):
        response = await client.post(
            "/interviews/sessions", json={"candidate_id": "not-an-objectid"}
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid candidate ID"

    async def test_rejects_unknown_candidate(self, client):
        response = await client.post(
            "/interviews/sessions", json={"candidate_id": str(ObjectId())}
        )

        assert response.status_code == 404

    async def test_rejects_candidate_not_invited_to_interview(
        self, client, fakes
    ):
        candidate_id = ObjectId()
        fakes.candidates.documents.append(
            {
                "_id": candidate_id,
                "job_id": str(ObjectId()),
                "decision": "rejected",
            }
        )

        response = await client.post(
            "/interviews/sessions", json={"candidate_id": str(candidate_id)}
        )

        assert response.status_code == 400
        assert "not eligible" in response.json()["detail"]


class TestGetSession:
    async def test_returns_questions_and_the_current_question(
        self, client, fakes
    ):
        session = create_interview_session_document(
            candidate_id=str(ObjectId()),
            job_id=str(ObjectId()),
            questions=[
                {"id": "question_1", "text": "One", "time_limit_seconds": 60},
                {"id": "question_2", "text": "Two", "time_limit_seconds": 90},
            ],
        )
        session["current_question_index"] = 1
        session["status"] = "in_progress"
        session["intro_acknowledged_at"] = datetime.utcnow()
        session["_id"] = ObjectId()
        fakes.sessions.documents.append(session)

        response = await client.get(f"/interviews/sessions/{session['_id']}")

        assert response.status_code == 200
        body = response.json()
        assert len(body["questions"]) == 2
        assert body["total_time_seconds"] == 150
        assert body["question"]["id"] == "question_2"

    async def test_omits_current_question_once_submitted(self, client, fakes):
        session = create_interview_session_document(
            candidate_id=str(ObjectId()),
            job_id=str(ObjectId()),
            questions=[
                {"id": "question_1", "text": "One", "time_limit_seconds": 60}
            ],
        )
        session["status"] = "submitted"
        session["_id"] = ObjectId()
        fakes.sessions.documents.append(session)

        response = await client.get(f"/interviews/sessions/{session['_id']}")

        body = response.json()
        assert body["status"] == "submitted"
        assert body["question"] is None
        assert len(body["questions"]) == 1

    async def test_rejects_malformed_session_id(self, client):
        response = await client.get("/interviews/sessions/nope")

        assert response.status_code == 400

    async def test_rejects_unknown_session(self, client):
        response = await client.get(f"/interviews/sessions/{ObjectId()}")

        assert response.status_code == 404

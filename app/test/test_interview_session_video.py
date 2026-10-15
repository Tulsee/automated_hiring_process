"""Tests for the single full-interview video upload."""

from datetime import datetime

from bson import ObjectId

from app.models.interview_session import create_interview_session_document

FULL_INTERVIEW = "__full_interview__"


def make_session(fakes, status="in_progress"):
    session = create_interview_session_document(
        candidate_id=str(ObjectId()),
        job_id=str(ObjectId()),
        questions=[
            {"id": "question_1", "text": "One", "time_limit_seconds": 60}
        ],
    )
    session["status"] = status
    session["_id"] = ObjectId()
    fakes.sessions.documents.append(session)
    return session


def video_file(content=b"fake-webm-bytes", content_type="video/webm"):
    return {"video": ("interview.webm", content, content_type)}


class TestUploadFullInterviewVideo:
    async def test_stores_one_video_and_submits_the_session(
        self, client, fakes, tmp_path
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        response = await client.post(
            "/interviews/session-video",
            data={"session_id": session_id},
            files=video_file(),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "submitted"
        assert body["filename"] == f"{session_id}{FULL_INTERVIEW}.webm"

        # exactly one answer record, and one file on disk
        assert len(fakes.answers.documents) == 1
        assert len(list(tmp_path.iterdir())) == 1
        assert (tmp_path / body["filename"]).read_bytes() == b"fake-webm-bytes"

        # the session is marked submitted
        assert session["status"] == "submitted"
        assert isinstance(session["submitted_at"], datetime)

    async def test_answer_record_timestamps_are_datetimes(
        self, client, fakes
    ):
        """Regression: `import datetime` + `datetime.utcnow()` raised
        AttributeError after the file had already been written."""
        session = make_session(fakes)

        response = await client.post(
            "/interviews/session-video",
            data={"session_id": str(session["_id"])},
            files=video_file(),
        )

        assert response.status_code == 200
        record = fakes.answers.documents[0]
        assert isinstance(record["created_at"], datetime)
        assert record["question_id"] == FULL_INTERVIEW

    async def test_accepts_mp4_and_uses_the_matching_extension(
        self, client, fakes
    ):
        session = make_session(fakes)

        response = await client.post(
            "/interviews/session-video",
            data={"session_id": str(session["_id"])},
            files=video_file(content_type="video/mp4"),
        )

        assert response.status_code == 200
        assert response.json()["filename"].endswith(".mp4")

    async def test_rejects_a_second_upload_for_the_same_session(
        self, client, fakes
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        first = await client.post(
            "/interviews/session-video",
            data={"session_id": session_id},
            files=video_file(),
        )
        assert first.status_code == 200

        # the session is now `submitted`, so re-upload is blocked there first
        session["status"] = "in_progress"

        second = await client.post(
            "/interviews/session-video",
            data={"session_id": session_id},
            files=video_file(),
        )

        assert second.status_code == 409
        assert len(fakes.answers.documents) == 1

    async def test_rejects_upload_when_session_is_not_in_progress(
        self, client, fakes
    ):
        session = make_session(fakes, status="submitted")

        response = await client.post(
            "/interviews/session-video",
            data={"session_id": str(session["_id"])},
            files=video_file(),
        )

        assert response.status_code == 400
        assert "not in progress" in response.json()["detail"]

    async def test_rejects_unsupported_content_type(self, client, fakes):
        session = make_session(fakes)

        response = await client.post(
            "/interviews/session-video",
            data={"session_id": str(session["_id"])},
            files=video_file(content_type="application/pdf"),
        )

        assert response.status_code == 400

    async def test_rejects_an_empty_video(self, client, fakes, tmp_path):
        session = make_session(fakes)

        response = await client.post(
            "/interviews/session-video",
            data={"session_id": str(session["_id"])},
            files=video_file(content=b""),
        )

        assert response.status_code == 400
        assert len(fakes.answers.documents) == 0

    async def test_rejects_malformed_session_id(self, client):
        response = await client.post(
            "/interviews/session-video",
            data={"session_id": "nope"},
            files=video_file(),
        )

        assert response.status_code == 400

    async def test_rejects_unknown_session(self, client):
        response = await client.post(
            "/interviews/session-video",
            data={"session_id": str(ObjectId())},
            files=video_file(),
        )

        assert response.status_code == 404

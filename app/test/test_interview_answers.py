"""Tests for per-question answer uploads.

One interview session holds several questions, and each question gets its own
recording. These tests pin that down: one video per question, each with its own
time limit, and the session only submits once every question is answered.
"""

from datetime import datetime

import pytest
from bson import ObjectId

from app.models.interview_session import create_interview_session_document

QUESTIONS = [
    {"id": "question_1", "text": "One", "time_limit_seconds": 60},
    {"id": "question_2", "text": "Two", "time_limit_seconds": 90},
    {"id": "question_3", "text": "Three", "time_limit_seconds": 120},
]


def make_session(fakes, questions=None, status="in_progress"):
    session = create_interview_session_document(
        candidate_id=str(ObjectId()),
        job_id=str(ObjectId()),
        questions=[dict(question) for question in (questions or QUESTIONS)],
    )
    session["status"] = status
    session["_id"] = ObjectId()
    fakes.sessions.documents.append(session)
    return session


def video(content=b"fake-webm-bytes", content_type="video/webm"):
    return {"answer": ("answer.webm", content, content_type)}


async def upload(client, session_id, question_id, **kwargs):
    return await client.post(
        "/interviews/answers",
        data={"session_id": session_id, "question_id": question_id},
        files=video(**kwargs),
    )


class TestOneVideoPerQuestion:
    async def test_each_question_stores_its_own_video(
        self, client, fakes, tmp_path
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        for question in QUESTIONS:
            response = await upload(client, session_id, question["id"])
            assert response.status_code == 200

        # three questions -> three records and three files
        assert len(fakes.answers.documents) == 3
        assert len(list(tmp_path.iterdir())) == 3

        filenames = sorted(path.name for path in tmp_path.iterdir())
        assert filenames == [
            f"{session_id}_question_1.webm",
            f"{session_id}_question_2.webm",
            f"{session_id}_question_3.webm",
        ]

    async def test_each_answer_records_its_own_time_limit(self, client, fakes):
        """Each question has a different time slot; the answer keeps it."""
        session = make_session(fakes)
        session_id = str(session["_id"])

        for question in QUESTIONS:
            await upload(client, session_id, question["id"])

        stored = {
            document["question_id"]: document["time_limit_seconds"]
            for document in fakes.answers.documents
        }

        assert stored == {
            "question_1": 60,
            "question_2": 90,
            "question_3": 120,
        }

    async def test_answer_keeps_the_question_index(self, client, fakes):
        session = make_session(fakes)

        await upload(client, str(session["_id"]), "question_2")

        assert fakes.answers.documents[0]["question_index"] == 1

    async def test_accepts_mp4_with_the_matching_extension(self, client, fakes):
        session = make_session(fakes)

        response = await upload(
            client, str(session["_id"]), "question_1", content_type="video/mp4"
        )

        assert response.status_code == 200
        assert response.json()["filename"].endswith(".mp4")

    @pytest.mark.parametrize(
        "content_type",
        [
            "video/webm;codecs=vp9,opus",
            "video/webm;codecs=vp8,opus",
            "video/webm; codecs=av01.0.05M.08,opus",
            "VIDEO/WEBM;codecs=vp9",
        ],
    )
    async def test_accepts_the_codec_suffix_mediarecorder_sends(
        self, client, fakes, content_type
    ):
        """MediaRecorder reports `video/webm;codecs=...`, not bare
        `video/webm`; the browser upload is rejected without this."""
        session = make_session(fakes)

        response = await upload(
            client, str(session["_id"]), "question_1", content_type=content_type
        )

        assert response.status_code == 200
        assert response.json()["filename"].endswith(".webm")

    async def test_mp4_with_a_codec_suffix_keeps_the_mp4_extension(
        self, client, fakes
    ):
        session = make_session(fakes)

        response = await upload(
            client,
            str(session["_id"]),
            "question_1",
            content_type="video/mp4;codecs=avc1.42E01E",
        )

        assert response.status_code == 200
        assert response.json()["filename"].endswith(".mp4")


class TestSessionProgress:
    async def test_reports_progress_and_the_next_question(self, client, fakes):
        session = make_session(fakes)
        session_id = str(session["_id"])

        first = (await upload(client, session_id, "question_1")).json()

        assert first["answered_count"] == 1
        assert first["total_questions"] == 3
        assert first["session_status"] == "in_progress"
        assert first["next_question"]["id"] == "question_2"
        assert first["next_question"]["time_limit_seconds"] == 90

        second = (await upload(client, session_id, "question_2")).json()

        assert second["answered_count"] == 2
        assert second["next_question"]["id"] == "question_3"

    async def test_session_stays_in_progress_until_every_question_answered(
        self, client, fakes
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        await upload(client, session_id, "question_1")
        await upload(client, session_id, "question_2")

        assert session["status"] == "in_progress"
        assert session["submitted_at"] is None

    async def test_session_submits_after_the_last_question(self, client, fakes):
        session = make_session(fakes)
        session_id = str(session["_id"])

        for question in QUESTIONS:
            last = await upload(client, session_id, question["id"])

        body = last.json()
        assert body["answered_count"] == 3
        assert body["session_status"] == "submitted"
        assert body["next_question"] is None

        assert session["status"] == "submitted"
        assert isinstance(session["submitted_at"], datetime)

    async def test_answers_may_arrive_out_of_order(self, client, fakes):
        session = make_session(fakes)
        session_id = str(session["_id"])

        third = (await upload(client, session_id, "question_3")).json()

        # the next question offered is the first one still unanswered
        assert third["next_question"]["id"] == "question_1"
        assert third["answered_count"] == 1

    async def test_timestamps_are_datetimes(self, client, fakes):
        session = make_session(fakes)

        await upload(client, str(session["_id"]), "question_1")

        assert isinstance(fakes.answers.documents[0]["created_at"], datetime)


class TestValidation:
    async def test_rejects_a_duplicate_answer_for_the_same_question(
        self, client, fakes
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        first = await upload(client, session_id, "question_1")
        assert first.status_code == 200

        second = await upload(client, session_id, "question_1")

        assert second.status_code == 409
        assert "already been answered" in second.json()["detail"]
        assert len(fakes.answers.documents) == 1

    async def test_rejects_a_question_outside_the_session(self, client, fakes):
        session = make_session(fakes)

        response = await upload(client, str(session["_id"]), "question_99")

        assert response.status_code == 404
        assert "does not belong" in response.json()["detail"]

    async def test_rejects_upload_once_the_session_is_submitted(
        self, client, fakes
    ):
        session = make_session(fakes, status="submitted")

        response = await upload(client, str(session["_id"]), "question_1")

        assert response.status_code == 400
        assert "not in progress" in response.json()["detail"]

    async def test_rejects_unsupported_content_type(self, client, fakes):
        session = make_session(fakes)

        response = await upload(
            client,
            str(session["_id"]),
            "question_1",
            content_type="application/pdf",
        )

        assert response.status_code == 400

    async def test_rejects_a_non_video_type_with_a_suffix(self, client, fakes):
        session = make_session(fakes)

        response = await upload(
            client,
            str(session["_id"]),
            "question_1",
            content_type="application/pdf;version=1.7",
        )

        assert response.status_code == 400

    async def test_rejects_an_empty_video(self, client, fakes):
        session = make_session(fakes)

        response = await upload(
            client, str(session["_id"]), "question_1", content=b""
        )

        assert response.status_code == 400
        assert len(fakes.answers.documents) == 0

    async def test_rejects_malformed_session_id(self, client):
        response = await upload(client, "nope", "question_1")

        assert response.status_code == 400

    async def test_rejects_unknown_session(self, client):
        response = await upload(client, str(ObjectId()), "question_1")

        assert response.status_code == 404


class TestDownloadAnswer:
    async def test_returns_the_video_for_one_question(self, client, fakes):
        session = make_session(fakes)
        session_id = str(session["_id"])

        await upload(client, session_id, "question_2")

        response = await client.get(
            f"/interviews/{session_id}/questions/question_2/answers"
        )

        assert response.status_code == 200
        assert response.content == b"fake-webm-bytes"

    async def test_unanswered_question_has_no_video(self, client, fakes):
        session = make_session(fakes)
        session_id = str(session["_id"])

        response = await client.get(
            f"/interviews/{session_id}/questions/question_1/answers"
        )

        assert response.status_code == 404

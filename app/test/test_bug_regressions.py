"""Regressions for bugs found by auditing the code.

Each test fails against the behaviour that was there before the fix.
"""

from datetime import datetime
from unittest.mock import patch

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.routes import interviews
from app.services.rubric import RubricError, validate_rubric


def descriptors(**overrides):
    base = {"descriptors": {1: "poor", 3: "ok", 5: "great"}}
    base.update(overrides)
    return base


class TestStartupSurvivesQdrantBeingDown:
    """The lifespan logged "starting with connections unavailable" and then
    crashed anyway, because create_collection was called unguarded."""

    async def test_create_collection_reports_failure_instead_of_raising(self):
        from app.services import qdrant_service

        async def boom(*args, **kwargs):
            raise ConnectionError("All connection attempts failed")

        with patch.object(qdrant_service.qdrant, "collection_exists", boom):
            result = await qdrant_service.create_collection()

        assert result is False

    async def test_the_collection_uses_the_configured_dimension(self):
        """Hardcoding 768 meant changing the setting silently broke upserts."""
        from app.core.config import settings
        from app.services import qdrant_service

        captured = {}

        async def exists(*args, **kwargs):
            return False

        async def create(collection_name, vectors_config, **kwargs):
            captured["size"] = vectors_config.size

        with patch.object(qdrant_service.qdrant, "collection_exists", exists):
            with patch.object(qdrant_service.qdrant, "create_collection", create):
                await qdrant_service.create_collection()

        assert captured["size"] == settings.EMBEDDING_DIMENSION


class TestRubricRejectsBadDescriptorsCleanly:
    """A non-numeric descriptor level leaked a bare ValueError, which surfaced
    as a 500 rather than the 400 the route is written to return."""

    def test_a_non_numeric_level_raises_rubric_error(self):
        with pytest.raises(RubricError, match="non-numeric"):
            validate_rubric(
                [
                    {"competency": "a", "descriptors": {"low": "x"}},
                    {"competency": "b", **descriptors()},
                    {"competency": "c", **descriptors()},
                ]
            )

    def test_a_level_outside_the_scale_raises_rubric_error(self):
        with pytest.raises(RubricError, match="outside"):
            validate_rubric(
                [
                    {"competency": "a", "descriptors": {0: "x", 9: "y"}},
                    {"competency": "b", **descriptors()},
                    {"competency": "c", **descriptors()},
                ]
            )

    async def test_the_route_turns_that_into_a_400(self, client, fakes):
        job_id = ObjectId()
        fakes.jobs.documents.append(
            {
                "_id": job_id,
                "interview_rubric": [
                    {"competency": "a", "descriptors": {"low": "x"}},
                    {"competency": "b", **descriptors()},
                    {"competency": "c", **descriptors()},
                ],
            }
        )

        session = {
            "_id": ObjectId(),
            "candidate_id": str(ObjectId()),
            "job_id": str(job_id),
            "questions": [
                {"id": "q1", "text": "One", "competency": "a",
                 "time_limit_seconds": 60}
            ],
            "current_question_index": 0,
            "total_time_seconds": 60,
            "status": "submitted",
        }
        fakes.sessions.documents.append(session)

        response = await client.post(
            f"/interviews/sessions/{session['_id']}/score"
        )

        assert response.status_code == 400


class TestUploadClaimsTheSlotBeforeWriting:
    """The video was written to a deterministic path before the insert, so a
    losing racer overwrote the stored answer and a failed insert orphaned a
    file."""

    async def make_session(self, fakes):
        session = {
            "_id": ObjectId(),
            "candidate_id": str(ObjectId()),
            "job_id": str(ObjectId()),
            # Two questions, so answering one does not submit the session
            # and the second upload reaches the duplicate check.
            "questions": [
                {
                    "id": "q1",
                    "text": "One",
                    "competency": "technical_depth",
                    "time_limit_seconds": 60,
                },
                {
                    "id": "q2",
                    "text": "Two",
                    "competency": "system_design",
                    "time_limit_seconds": 90,
                },
            ],
            "current_question_index": 0,
            "total_time_seconds": 150,
            "status": "in_progress",
            "intro_acknowledged_at": datetime.utcnow(),
        }
        fakes.sessions.documents.append(session)
        return session

    async def test_a_rejected_duplicate_does_not_overwrite_the_stored_video(
        self, client, fakes, tmp_path, monkeypatch
    ):
        session = await self.make_session(fakes)
        session_id = str(session["_id"])

        first = await client.post(
            "/interviews/answers",
            data={"session_id": session_id, "question_id": "q1"},
            files={"answer": ("a.webm", b"ORIGINAL-CONTENT", "video/webm")},
        )
        assert first.status_code == 200

        stored = tmp_path / f"{session_id}_q1.webm"
        assert stored.read_bytes() == b"ORIGINAL-CONTENT"

        # Force the race outcome: the duplicate check passes, the insert loses.
        real_find_one = fakes.answers.find_one

        async def pretend_absent(query):
            if "question_id" in query:
                return None
            return await real_find_one(query)

        async def reject(document):
            raise DuplicateKeyError("duplicate")

        monkeypatch.setattr(fakes.answers, "find_one", pretend_absent)
        monkeypatch.setattr(fakes.answers, "insert_one", reject)

        second = await client.post(
            "/interviews/answers",
            data={"session_id": session_id, "question_id": "q1"},
            files={"answer": ("a.webm", b"LOSER-CONTENT", "video/webm")},
        )

        assert second.status_code == 409
        # The winner's recording must still be the one on disk.
        assert stored.read_bytes() == b"ORIGINAL-CONTENT"

    async def test_a_failed_file_write_leaves_no_database_record(
        self, client, fakes, monkeypatch
    ):
        session = await self.make_session(fakes)

        real_open = open

        def failing_open(path, mode="r", *args, **kwargs):
            if "w" in mode and str(path).endswith(".webm"):
                raise OSError("disk full")
            return real_open(path, mode, *args, **kwargs)

        monkeypatch.setattr("builtins.open", failing_open)

        response = await client.post(
            "/interviews/answers",
            data={"session_id": str(session["_id"]), "question_id": "q1"},
            files={"answer": ("a.webm", b"content", "video/webm")},
        )

        assert response.status_code == 500
        assert fakes.answers.documents == []


class TestCachedScoresFollowTheCurrentRubric:
    """A stored score carried the competency it was scored under, which
    overrode the current rubric when a cached score was reused."""

    async def test_a_reused_score_is_counted_under_the_current_competency(
        self, client, fakes, monkeypatch
    ):
        session = {
            "_id": ObjectId(),
            "candidate_id": str(ObjectId()),
            "job_id": str(ObjectId()),
            "questions": [
                {
                    "id": "q1",
                    "text": "One",
                    "competency": "system_design",
                    "time_limit_seconds": 60,
                }
            ],
            "current_question_index": 0,
            "total_time_seconds": 60,
            "status": "submitted",
        }
        fakes.sessions.documents.append(session)

        # An answer scored earlier, when the question tested something else.
        fakes.answers.documents.append(
            {
                "_id": ObjectId(),
                "session_id": str(session["_id"]),
                "question_id": "q1",
                "question_index": 0,
                "transcript": "word " * 20,
                "transcription_status": "completed",
                "score_result": {
                    "competency": "technical_depth",
                    "score": 4,
                    "evidence_quote": "word word",
                    "quote_verified": True,
                    "reasoning": "Scored under the old rubric.",
                    "answers_question": True,
                    "flags": [],
                    "model": "stub",
                },
            }
        )

        body = (
            await client.post(
                f"/interviews/sessions/{session['_id']}/score"
            )
        ).json()

        competencies = [
            score["competency"] for score in body["answer_scores"]
        ]

        assert competencies == ["system_design"]
        assert [
            entry["competency"]
            for entry in body["scorecard"]["competency_scores"]
        ] == ["system_design"]

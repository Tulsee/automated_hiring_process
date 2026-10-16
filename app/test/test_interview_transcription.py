"""Tests for the transcription endpoints (Module 14).

Whisper itself is replaced with a stub here so the suite stays fast and
offline; the real model is exercised by `check_transcription.py`.
"""

from datetime import datetime

import pytest
from bson import ObjectId

from app.routes import interviews
from app.services.audio_service import AudioExtractionError
from app.services.transcription_service import TranscriptionError

QUESTIONS = [
    {
        "id": "question_1",
        "text": "One",
        "competency": "technical_depth",
        "time_limit_seconds": 60,
    },
    {
        "id": "question_2",
        "text": "Two",
        "competency": "system_design",
        "time_limit_seconds": 90,
    },
]


def make_session(fakes, status="submitted"):
    session = {
        "_id": ObjectId(),
        "candidate_id": str(ObjectId()),
        "job_id": str(ObjectId()),
        "questions": [dict(question) for question in QUESTIONS],
        "current_question_index": 1,
        "total_time_seconds": 150,
        "status": status,
        "intro_acknowledged_at": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "submitted_at": datetime.utcnow(),
    }
    fakes.sessions.documents.append(session)
    return session


def add_answer(fakes, session_id, question_id, index, **extra):
    answer = {
        "_id": ObjectId(),
        "session_id": session_id,
        "question_id": question_id,
        "question_index": index,
        "filename": f"{session_id}_{question_id}.webm",
        "file_path": f"uploads/interview_answers/{session_id}_{question_id}.webm",
        "status": "uploaded",
        "created_at": datetime.utcnow(),
        **extra,
    }
    fakes.answers.documents.append(answer)
    return answer


def fake_transcript(text="I build backend services in Python and FastAPI.", **extra):
    return {
        "text": text,
        "segments": [
            {
                "start": 0.0,
                "end": 3.2,
                "text": text,
                "avg_logprob": -0.2,
                "no_speech_prob": 0.01,
            }
        ],
        "language": "en",
        "language_probability": 0.99,
        "duration_seconds": 3.2,
        "word_count": len(text.split()),
        "model": "base",
        "flags": [],
        "audio_path": "uploads/interview_audio/x.wav",
        **extra,
    }


@pytest.fixture
def stub_whisper(monkeypatch):
    """Replace transcription with a stub, recording what it was asked to do."""
    calls = []

    async def fake(video_path):
        calls.append(str(video_path))
        return fake_transcript()

    monkeypatch.setattr(interviews, "transcribe_answer", fake)

    return calls


class TestTranscribeSession:
    async def test_transcribes_every_answer(self, client, fakes, stub_whisper):
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)
        add_answer(fakes, session_id, "question_2", 1)

        response = await client.post(f"/interviews/sessions/{session_id}/transcribe")

        assert response.status_code == 200
        body = response.json()

        assert body["transcribed"] == 2
        assert body["failed"] == 0
        assert body["transcription_status"] == "completed"
        assert len(stub_whisper) == 2

    async def test_stores_the_transcript_on_the_answer(
        self, client, fakes, stub_whisper
    ):
        """Done when: every answer has a stored, readable transcript."""
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)

        await client.post(f"/interviews/sessions/{session_id}/transcribe")

        stored = fakes.answers.documents[0]

        assert stored["transcript"].startswith("I build backend services")
        assert stored["transcript_word_count"] == 8
        assert stored["transcript_language"] == "en"
        assert stored["transcript_model"] == "base"
        assert stored["transcription_status"] == "completed"
        assert isinstance(stored["transcribed_at"], datetime)

    async def test_keeps_the_audio_path(self, client, fakes, stub_whisper):
        """The audio is kept so a suspect transcript can be checked."""
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)

        await client.post(f"/interviews/sessions/{session_id}/transcribe")

        assert fakes.answers.documents[0]["audio_path"].endswith(".wav")

    async def test_stores_segments_for_spot_checking(
        self, client, fakes, stub_whisper
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)

        await client.post(f"/interviews/sessions/{session_id}/transcribe")

        segments = fakes.answers.documents[0]["transcript_segments"]

        assert len(segments) == 1
        assert segments[0]["avg_logprob"] == -0.2

    async def test_marks_the_session_transcribed(
        self, client, fakes, stub_whisper
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)
        add_answer(fakes, session_id, "question_2", 1)

        await client.post(f"/interviews/sessions/{session_id}/transcribe")

        assert session["transcription_status"] == "completed"
        assert isinstance(session["transcribed_at"], datetime)

    async def test_a_partly_answered_session_is_only_partial(
        self, client, fakes, stub_whisper
    ):
        """Two questions but one answer must not read as completed."""
        session = make_session(fakes, status="in_progress")
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)

        body = (
            await client.post(f"/interviews/sessions/{session_id}/transcribe")
        ).json()

        assert body["transcribed"] == 1
        assert body["transcription_status"] == "partial"

    async def test_rerunning_skips_answers_already_transcribed(
        self, client, fakes, stub_whisper
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)
        add_answer(fakes, session_id, "question_2", 1)

        await client.post(f"/interviews/sessions/{session_id}/transcribe")

        second = (
            await client.post(f"/interviews/sessions/{session_id}/transcribe")
        ).json()

        assert second["skipped"] == 2
        assert second["transcribed"] == 0
        # The expensive work ran only once.
        assert len(stub_whisper) == 2

    async def test_force_retranscribes(self, client, fakes, stub_whisper):
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)

        await client.post(f"/interviews/sessions/{session_id}/transcribe")

        body = (
            await client.post(
                f"/interviews/sessions/{session_id}/transcribe?force=true"
            )
        ).json()

        assert body["transcribed"] == 1
        assert body["skipped"] == 0
        assert len(stub_whisper) == 2

    async def test_answers_are_processed_in_question_order(
        self, client, fakes, stub_whisper
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        # inserted out of order
        add_answer(fakes, session_id, "question_2", 1)
        add_answer(fakes, session_id, "question_1", 0)

        body = (
            await client.post(f"/interviews/sessions/{session_id}/transcribe")
        ).json()

        assert [result["question_id"] for result in body["results"]] == [
            "question_1",
            "question_2",
        ]

    async def test_a_session_with_no_answers_is_rejected(self, client, fakes):
        session = make_session(fakes)

        response = await client.post(
            f"/interviews/sessions/{session['_id']}/transcribe"
        )

        assert response.status_code == 400
        assert "no answers" in response.json()["detail"]

    async def test_rejects_an_unknown_session(self, client):
        response = await client.post(
            f"/interviews/sessions/{ObjectId()}/transcribe"
        )

        assert response.status_code == 404

    async def test_rejects_a_malformed_session_id(self, client):
        response = await client.post("/interviews/sessions/nope/transcribe")

        assert response.status_code == 400


class TestTranscriptionFailures:
    async def test_one_failure_does_not_stop_the_others(
        self, client, fakes, monkeypatch
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)
        add_answer(fakes, session_id, "question_2", 1)

        async def flaky(video_path):
            if "question_1" in str(video_path):
                raise AudioExtractionError("no audio track")
            return fake_transcript()

        monkeypatch.setattr(interviews, "transcribe_answer", flaky)

        body = (
            await client.post(f"/interviews/sessions/{session_id}/transcribe")
        ).json()

        assert body["failed"] == 1
        assert body["transcribed"] == 1
        assert body["transcription_status"] == "partial"

        failed = next(r for r in body["results"] if r["status"] == "failed")
        assert "no audio track" in failed["error"]

    async def test_a_failure_is_recorded_on_the_answer(
        self, client, fakes, monkeypatch
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)

        async def broken(video_path):
            raise TranscriptionError("model exploded")

        monkeypatch.setattr(interviews, "transcribe_answer", broken)

        await client.post(f"/interviews/sessions/{session_id}/transcribe")

        stored = fakes.answers.documents[0]

        assert stored["transcription_status"] == "failed"
        assert stored["transcription_error"] == "model exploded"
        assert "transcript" not in stored

    async def test_everything_failing_reports_failed(
        self, client, fakes, monkeypatch
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)

        async def broken(video_path):
            raise AudioExtractionError("ffmpeg missing")

        monkeypatch.setattr(interviews, "transcribe_answer", broken)

        body = (
            await client.post(f"/interviews/sessions/{session_id}/transcribe")
        ).json()

        assert body["transcription_status"] == "failed"


class TestGetTranscripts:
    async def test_returns_transcripts_with_their_questions(
        self, client, fakes, stub_whisper
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)
        add_answer(fakes, session_id, "question_2", 1)

        await client.post(f"/interviews/sessions/{session_id}/transcribe")

        response = await client.get(
            f"/interviews/sessions/{session_id}/transcripts"
        )

        assert response.status_code == 200
        body = response.json()

        assert body["transcribed_count"] == 2
        assert body["transcription_status"] == "completed"

        first = body["transcripts"][0]
        assert first["question_id"] == "question_1"
        assert first["question_text"] == "One"
        # The competency carries through for Module 15's rubric scoring.
        assert first["competency"] == "technical_depth"
        assert first["transcript"]

    async def test_transcripts_come_back_in_question_order(
        self, client, fakes, stub_whisper
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_2", 1)
        add_answer(fakes, session_id, "question_1", 0)

        await client.post(f"/interviews/sessions/{session_id}/transcribe")

        body = (
            await client.get(f"/interviews/sessions/{session_id}/transcripts")
        ).json()

        assert [t["question_id"] for t in body["transcripts"]] == [
            "question_1",
            "question_2",
        ]

    async def test_segments_are_omitted_unless_asked_for(
        self, client, fakes, stub_whisper
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)

        await client.post(f"/interviews/sessions/{session_id}/transcribe")

        without = (
            await client.get(f"/interviews/sessions/{session_id}/transcripts")
        ).json()

        with_segments = (
            await client.get(
                f"/interviews/sessions/{session_id}/transcripts"
                "?include_segments=true"
            )
        ).json()

        assert without["transcripts"][0]["segments"] == []
        assert len(with_segments["transcripts"][0]["segments"]) == 1

    async def test_untranscribed_answers_are_left_out(self, client, fakes):
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)

        body = (
            await client.get(f"/interviews/sessions/{session_id}/transcripts")
        ).json()

        assert body["transcribed_count"] == 0
        assert body["transcripts"] == []
        assert body["transcription_status"] == "pending"

    async def test_flags_are_exposed(self, client, fakes, monkeypatch):
        """A human needs to see which transcripts are suspect."""
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)

        async def thin(video_path):
            return fake_transcript(
                text="Thank you.", flags=["transcript_too_short"]
            )

        monkeypatch.setattr(interviews, "transcribe_answer", thin)

        await client.post(f"/interviews/sessions/{session_id}/transcribe")

        body = (
            await client.get(f"/interviews/sessions/{session_id}/transcripts")
        ).json()

        assert body["transcripts"][0]["flags"] == ["transcript_too_short"]

    async def test_rejects_an_unknown_session(self, client):
        response = await client.get(
            f"/interviews/sessions/{ObjectId()}/transcripts"
        )

        assert response.status_code == 404


class TestEmptyTranscripts:
    """A silent answer transcribes to "" - a real result, not a missing one."""

    @staticmethod
    def stub_empty(monkeypatch):
        async def empty(video_path):
            return fake_transcript(text="", flags=["empty_transcript"])

        monkeypatch.setattr(interviews, "transcribe_answer", empty)

    async def test_an_empty_transcript_is_not_retranscribed(
        self, client, fakes, monkeypatch
    ):
        """Regression: `""` is falsy, so the skip check redid the work every
        run and burned minutes of CPU on every silent answer."""
        calls = []

        async def empty(video_path):
            calls.append(str(video_path))
            return fake_transcript(text="", flags=["empty_transcript"])

        monkeypatch.setattr(interviews, "transcribe_answer", empty)

        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)

        await client.post(f"/interviews/sessions/{session_id}/transcribe")

        second = (
            await client.post(f"/interviews/sessions/{session_id}/transcribe")
        ).json()

        assert second["skipped"] == 1
        assert second["transcribed"] == 0
        assert len(calls) == 1

    async def test_an_empty_transcript_is_still_returned(
        self, client, fakes, monkeypatch
    ):
        """Regression: the flagged answer a human most needs to review was the
        one filtered out of the transcripts listing."""
        self.stub_empty(monkeypatch)

        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)

        await client.post(f"/interviews/sessions/{session_id}/transcribe")

        body = (
            await client.get(f"/interviews/sessions/{session_id}/transcripts")
        ).json()

        assert body["transcribed_count"] == 1
        assert body["transcripts"][0]["transcript"] == ""
        assert body["transcripts"][0]["flags"] == ["empty_transcript"]

    async def test_counts_agree_when_an_answer_is_silent(
        self, client, fakes, monkeypatch
    ):
        """Regression: status said `completed` while the count said 1 of 2."""
        async def mixed(video_path):
            if "question_2" in str(video_path):
                return fake_transcript(text="", flags=["empty_transcript"])
            return fake_transcript()

        monkeypatch.setattr(interviews, "transcribe_answer", mixed)

        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)
        add_answer(fakes, session_id, "question_2", 1)

        await client.post(f"/interviews/sessions/{session_id}/transcribe")

        body = (
            await client.get(f"/interviews/sessions/{session_id}/transcripts")
        ).json()

        assert body["transcription_status"] == "completed"
        assert body["transcribed_count"] == body["total_questions"] == 2

    async def test_a_failed_answer_is_excluded_from_transcripts(
        self, client, fakes, monkeypatch
    ):
        """A failure is different from an empty result and must not appear."""
        async def broken(video_path):
            raise AudioExtractionError("no audio track")

        monkeypatch.setattr(interviews, "transcribe_answer", broken)

        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)

        await client.post(f"/interviews/sessions/{session_id}/transcribe")

        body = (
            await client.get(f"/interviews/sessions/{session_id}/transcripts")
        ).json()

        assert body["transcribed_count"] == 0
        assert body["transcripts"] == []

    async def test_a_failed_answer_is_retried_on_the_next_run(
        self, client, fakes, monkeypatch
    ):
        """Only completed work is skipped, so a failure can be re-attempted."""
        attempts = []

        async def flaky(video_path):
            attempts.append(str(video_path))

            if len(attempts) == 1:
                raise AudioExtractionError("transient ffmpeg failure")

            return fake_transcript()

        monkeypatch.setattr(interviews, "transcribe_answer", flaky)

        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "question_1", 0)

        first = (
            await client.post(f"/interviews/sessions/{session_id}/transcribe")
        ).json()

        second = (
            await client.post(f"/interviews/sessions/{session_id}/transcribe")
        ).json()

        assert first["failed"] == 1
        assert second["transcribed"] == 1
        assert second["skipped"] == 0
        assert len(attempts) == 2

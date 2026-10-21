from pathlib import Path
import logging
from datetime import datetime
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from fastapi import (
    File,
    Form,
    UploadFile,
)
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import require_permission
from fastapi.responses import FileResponse

from app.db.mongodb import (
    interview_answers_collections,
    candidates_collection,
    interview_sessions_collection,
    jobs_collection,
)
from app.schemas.interview import (
    InterviewSessionResponse,
    CreateInterviewSessionResponse,
    CreateInterviewSessionRequest,
    AcknowledgeIntroResponse,
    InterviewQuestion,
    UploadAnswerResponse,
    AnswerTranscript,
    TranscribeAnswerResult,
    TranscribeSessionResponse,
    SessionTranscriptsResponse,
    AnswerScore,
    Scorecard,
    ScoreSessionResponse,
    ScorecardResponse,
    InterviewSessionSummary,
    InterviewSessionListResponse,
)

from app.models.interview_answer import create_interview_answer_document
from app.models.interview_session import (
    STATUS_IN_PROGRESS,
    STATUS_INVITED,
)
from app.services.interview_service import (
    create_session_for_candidate,
    invite_is_expired,
    is_eligible_for_interview,
)
from app.services.transcription_service import (
    TranscriptionError,
    transcribe_answer,
)
from app.services.audio_service import AudioExtractionError
from app.services.notifications import KIND_REVIEW, notify_administration
from app.services.answer_scoring_service import score_answer
from app.services.rubric import RubricError, entry_for_competency, get_rubric_for_job
from app.services.scorecard_service import (
    FLAG_NOT_TRANSCRIBED,
    FLAG_UNANSWERED,
    build_scorecard,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/interviews",
    tags=["interviews"],
)

ANSWER_UPLOAD_DIR = Path("uploads/interview_answers")
ANSWER_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_VIDEO_TYPES = {
    "video/webm",
    "video/mp4",
}


@router.post("/answers", response_model=UploadAnswerResponse)
async def upload_interview_answer(
    session_id: str = Form(...),
    question_id: str = Form(...),
    answer: UploadFile = File(...),
):
    """Upload the recording for ONE question of a session.

    Each question in a session gets its own video, so this is called once per
    question. The session advances as answers arrive and is marked `submitted`
    once every question has a video.
    """
    if not ObjectId.is_valid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID")

    session = await interview_sessions_collection.find_one(
        {"_id": ObjectId(session_id)}
    )

    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")

    if session["status"] == STATUS_INVITED:
        raise HTTPException(
            status_code=403,
            detail="Accept the interview intro before recording",
        )

    if session["status"] != STATUS_IN_PROGRESS:
        raise HTTPException(
            status_code=400, detail="Interview session is not in progress"
        )

    questions = session["questions"]

    question_index = next(
        (
            index
            for index, question in enumerate(questions)
            if question["id"] == question_id
        ),
        None,
    )

    if question_index is None:
        raise HTTPException(
            status_code=404,
            detail="Question does not belong to this interview session",
        )

    existing_answer = await interview_answers_collections.find_one(
        {"session_id": session_id, "question_id": question_id}
    )

    if existing_answer:
        raise HTTPException(
            status_code=409,
            detail="This question has already been answered",
        )

    # MediaRecorder sends the codec with the type, e.g.
    # "video/webm;codecs=vp9,opus", so compare the media type alone.
    media_type = (answer.content_type or "").split(";")[0].strip().lower()

    if media_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=400, detail="Only WebM or MP4 video is allowed."
        )

    content = await answer.read()

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded video is empty")

    extension = ".mp4" if media_type == "video/mp4" else ".webm"

    filename = f"{session_id}_{question_id}{extension}"

    file_path = ANSWER_UPLOAD_DIR / filename

    document = create_interview_answer_document(
        session_id=session_id,
        question_id=question_id,
        filename=filename,
        file_path=str(file_path),
        question_index=question_index,
        time_limit_seconds=questions[question_index]["time_limit_seconds"],
    )

    # Claim the slot in the database before touching disk. The filename is
    # derived from the question, so two racing uploads target the same path:
    # if the file were written first, the upload that loses the race would
    # overwrite the stored answer and then be rejected. Inserting first also
    # means a failed insert leaves no orphan file behind.
    try:
        result = await interview_answers_collections.insert_one(document)

    except DuplicateKeyError:
        logger.warning(
            "Duplicate answer rejected by index: %s/%s", session_id, question_id
        )

        raise HTTPException(
            status_code=409,
            detail="This question has already been answered",
        ) from None

    try:
        with open(file_path, "wb") as f:
            f.write(content)

    except OSError as error:
        # Without the recording the record is useless, so do not leave it.
        await interview_answers_collections.delete_one({"_id": result.inserted_id})

        logger.error("Could not save answer %s: %s", file_path, error)

        raise HTTPException(
            status_code=500, detail="Could not save the uploaded video"
        ) from error

    logger.info("Interview answer saved: %s", file_path)

    logger.info("Interview answer document inserted with ID: %s", result.inserted_id)

    # Advance the session by how many questions now have a video.
    answered_count = await interview_answers_collections.count_documents(
        {"session_id": session_id}
    )

    all_answered = answered_count >= len(questions)

    session_status = "submitted" if all_answered else "in_progress"

    updates = {
        "current_question_index": min(answered_count, len(questions) - 1),
        "status": session_status,
        "updated_at": datetime.utcnow(),
    }

    if all_answered:
        updates["submitted_at"] = datetime.utcnow()

    await interview_sessions_collection.update_one(
        {"_id": ObjectId(session_id)}, {"$set": updates}
    )

    # When the last answer lands, the interview is ready for a human to review.
    if all_answered:
        await notify_administration(
            KIND_REVIEW,
            "An interview is ready to review",
            "A candidate has submitted all of their interview answers.",
        )

    next_question = None

    if not all_answered:
        answered_ids = {
            document["question_id"]
            async for document in interview_answers_collections.find(
                {"session_id": session_id}, {"question_id": 1}
            )
        }

        next_question = next(
            (
                InterviewQuestion(**question)
                for question in questions
                if question["id"] not in answered_ids
            ),
            None,
        )

    return UploadAnswerResponse(
        id=str(result.inserted_id),
        session_id=session_id,
        question_id=question_id,
        filename=filename,
        status="uploaded",
        answered_count=answered_count,
        total_questions=len(questions),
        session_status=session_status,
        next_question=next_question,
    )


@router.get(
    "/{session_id}/questions/{question_id}/answers",
    dependencies=[Depends(require_permission("interviews:read"))],
)
async def get_interview_answer(session_id: str, question_id: str):
    answer = await interview_answers_collections.find_one(
        {
            "session_id": session_id,
            "question_id": question_id,
        }
    )

    if not answer:
        raise HTTPException(
            status_code=404,
            detail="Interview answer not found.",
        )

    file_path = Path(answer["file_path"])

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Video file not found",
        )

    return FileResponse(
        path=file_path,
        media_type="video/webm",
        filename=answer["filename"],
    )


def session_response(session: dict, session_id: str | None = None):
    """Shared shape for every endpoint that returns a session."""
    questions = session["questions"]

    current_index = session["current_question_index"]

    current_question = None

    if session["status"] == STATUS_IN_PROGRESS and current_index < len(questions):
        current_question = InterviewQuestion(**questions[current_index])

    return {
        "id": session_id or str(session["_id"]),
        "candidate_id": session["candidate_id"],
        "job_id": str(session["job_id"]),
        "current_question_index": current_index,
        "total_questions": len(questions),
        "total_time_seconds": session["total_time_seconds"],
        "status": session["status"],
        "questions": [InterviewQuestion(**question) for question in questions],
        "question": current_question,
        "intro_acknowledged": session.get("intro_acknowledged_at") is not None,
        "invite_expires_at": session.get("invite_expires_at"),
    }


async def get_session_by_token(token: str) -> dict:
    """Resolve an invite token to a usable session, or raise."""
    session = await interview_sessions_collection.find_one({"invite_token": token})

    if not session:
        raise HTTPException(status_code=404, detail="Invalid interview invite link")

    if invite_is_expired(session):
        raise HTTPException(
            status_code=410, detail="This interview invite link has expired"
        )

    return session


@router.post(
    "/sessions",
    response_model=CreateInterviewSessionResponse,
    dependencies=[Depends(require_permission("interviews:manage"))],
)
async def create_interview_session(
    data: CreateInterviewSessionRequest,
):
    """Invite a screened candidate: create their session and invite link."""
    if not ObjectId.is_valid(data.candidate_id):
        raise HTTPException(status_code=400, detail="Invalid candidate ID")

    candidate = await candidates_collection.find_one(
        {"_id": ObjectId(data.candidate_id)}
    )

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if not is_eligible_for_interview(candidate):
        raise HTTPException(
            status_code=400,
            detail="Candidate is not eligible for an interview session",
        )

    created = await create_session_for_candidate(candidate)

    return CreateInterviewSessionResponse(
        **session_response(created["session"], created["session_id"]),
        invite_token=created["invite_token"],
        invite_url=created["invite_url"],
    )


# List interview sessions
@router.get(
    "/sessions",
    response_model=InterviewSessionListResponse,
    dependencies=[Depends(require_permission("interviews:read"))],
)
async def list_interview_sessions(
    status: str | None = Query(
        None, description="invited, in_progress or submitted"
    ),
    candidate_id: str | None = Query(None),
    job_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List interview sessions, most recent first.

    This is how you find a `session_id` for the transcribe, transcripts, score
    and scorecard endpoints.
    """
    query: dict = {}

    if status is not None:
        query["status"] = status

    if candidate_id is not None:
        query["candidate_id"] = candidate_id

    if job_id is not None:
        query["job_id"] = job_id

    total = await interview_sessions_collection.count_documents(query)

    cursor = (
        interview_sessions_collection.find(query)
        .sort([("created_at", -1)])
        .skip(offset)
        .limit(limit)
    )

    sessions = []

    async for session in cursor:
        session_id = str(session["_id"])

        answered_count = await interview_answers_collections.count_documents(
            {"session_id": session_id}
        )

        candidate = None

        if ObjectId.is_valid(session.get("candidate_id", "")):
            candidate = await candidates_collection.find_one(
                {"_id": ObjectId(session["candidate_id"])}
            )

        job = None

        if ObjectId.is_valid(str(session.get("job_id", ""))):
            job = await jobs_collection.find_one(
                {"_id": ObjectId(str(session["job_id"]))}
            )

        scorecard = session.get("scorecard") or {}

        sessions.append(
            InterviewSessionSummary(
                id=session_id,
                candidate_id=session.get("candidate_id", ""),
                candidate_name=(candidate or {}).get("name"),
                job_id=str(session.get("job_id", "")),
                job_title=(job or {}).get("title"),
                status=session.get("status", STATUS_INVITED),
                total_questions=len(session.get("questions") or []),
                answered_count=answered_count,
                transcription_status=session.get("transcription_status"),
                scoring_status=session.get("scoring_status"),
                overall_score=scorecard.get("overall_score"),
                needs_human_review=scorecard.get("needs_human_review"),
                invite_expires_at=session.get("invite_expires_at"),
                created_at=session.get("created_at"),
                submitted_at=session.get("submitted_at"),
            )
        )

    return InterviewSessionListResponse(
        total=total,
        count=len(sessions),
        limit=limit,
        offset=offset,
        status=status,
        candidate_id=candidate_id,
        job_id=job_id,
        sessions=sessions,
    )


# Get Interview Session
@router.get(
    "/sessions/{session_id}",
    response_model=InterviewSessionResponse,
    dependencies=[Depends(require_permission("interviews:read"))],
)
async def get_interview_session(session_id: str):
    if not ObjectId.is_valid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID")

    session = await interview_sessions_collection.find_one(
        {"_id": ObjectId(session_id)}
    )

    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")

    return InterviewSessionResponse(**session_response(session))


# Open an interview from the invite link
@router.get("/invite/{token}", response_model=InterviewSessionResponse)
async def get_interview_session_by_invite(token: str):
    """What the candidate's intro screen loads. Does not start recording."""
    session = await get_session_by_token(token)

    return InterviewSessionResponse(**session_response(session))


# Accept the intro screen, which unlocks recording
@router.post("/invite/{token}/acknowledge", response_model=AcknowledgeIntroResponse)
async def acknowledge_interview_intro(token: str):
    """The candidate accepts the intro; the session becomes recordable."""
    session = await get_session_by_token(token)

    questions = session["questions"]

    if session["status"] == STATUS_INVITED:
        now = datetime.utcnow()

        await interview_sessions_collection.update_one(
            {"_id": session["_id"]},
            {
                "$set": {
                    "status": STATUS_IN_PROGRESS,
                    "intro_acknowledged_at": now,
                    "updated_at": now,
                }
            },
        )

        session["status"] = STATUS_IN_PROGRESS

        session["intro_acknowledged_at"] = now

        logger.info("Interview intro acknowledged: %s", session["_id"])

    current_index = session["current_question_index"]

    current_question = None

    if session["status"] == STATUS_IN_PROGRESS and current_index < len(questions):
        current_question = InterviewQuestion(**questions[current_index])

    return AcknowledgeIntroResponse(
        session_id=str(session["_id"]),
        status=session["status"],
        intro_acknowledged=session.get("intro_acknowledged_at") is not None,
        total_questions=len(questions),
        total_time_seconds=session["total_time_seconds"],
        question=current_question,
    )


# --------------------------------------------------------------------------
# Module 14 - audio extraction + transcription
# --------------------------------------------------------------------------

TRANSCRIPTION_PENDING = "pending"
TRANSCRIPTION_PARTIAL = "partial"
TRANSCRIPTION_COMPLETED = "completed"
TRANSCRIPTION_FAILED = "failed"


def question_by_id(session: dict) -> dict:
    return {question["id"]: question for question in session["questions"]}


async def load_session_or_404(session_id: str) -> dict:
    if not ObjectId.is_valid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID")

    session = await interview_sessions_collection.find_one(
        {"_id": ObjectId(session_id)}
    )

    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")

    return session


def transcription_status_for(transcribed: int, total: int, failed: int) -> str:
    if total == 0:
        return TRANSCRIPTION_PENDING

    if transcribed == 0:
        return TRANSCRIPTION_FAILED if failed else TRANSCRIPTION_PENDING

    if transcribed < total:
        return TRANSCRIPTION_PARTIAL

    return TRANSCRIPTION_COMPLETED


@router.post(
    "/sessions/{session_id}/transcribe",
    response_model=TranscribeSessionResponse,
    dependencies=[Depends(require_permission("interviews:manage"))],
)
async def transcribe_interview_session(session_id: str, force: bool = False):
    """Extract audio from every answer in a session and transcribe it.

    Safe to re-run: answers that already have a transcript are skipped unless
    `force=true`. One answer failing does not abandon the rest.
    """
    session = await load_session_or_404(session_id)

    questions = question_by_id(session)

    answers = [
        answer
        async for answer in interview_answers_collections.find(
            {"session_id": session_id}
        )
    ]

    if not answers:
        raise HTTPException(
            status_code=400, detail="This session has no answers to transcribe"
        )

    answers.sort(key=lambda answer: answer.get("question_index") or 0)

    results: list[TranscribeAnswerResult] = []

    transcribed = 0
    skipped = 0
    failed = 0

    for answer in answers:
        question_id = answer["question_id"]

        already_done = (
            answer.get("transcription_status") == TRANSCRIPTION_COMPLETED
        )

        if already_done and not force:
            skipped += 1

            results.append(
                TranscribeAnswerResult(
                    question_id=question_id,
                    status="skipped",
                    word_count=answer.get("transcript_word_count"),
                    flags=answer.get("transcript_flags") or [],
                )
            )

            continue

        try:
            transcript = await transcribe_answer(answer["file_path"])

        except (TranscriptionError, AudioExtractionError) as error:
            failed += 1

            logger.error(
                "Transcription failed for %s/%s: %s",
                session_id,
                question_id,
                error,
            )

            await interview_answers_collections.update_one(
                {"_id": answer["_id"]},
                {
                    "$set": {
                        "transcription_status": TRANSCRIPTION_FAILED,
                        "transcription_error": str(error),
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            results.append(
                TranscribeAnswerResult(
                    question_id=question_id,
                    status="failed",
                    error=str(error),
                )
            )

            continue

        now = datetime.utcnow()

        await interview_answers_collections.update_one(
            {"_id": answer["_id"]},
            {
                "$set": {
                    "transcript": transcript["text"],
                    "transcript_segments": transcript["segments"],
                    "transcript_language": transcript["language"],
                    "transcript_language_probability": transcript[
                        "language_probability"
                    ],
                    "transcript_word_count": transcript["word_count"],
                    "transcript_flags": transcript["flags"],
                    "transcript_model": transcript["model"],
                    "audio_path": transcript["audio_path"],
                    "audio_duration_seconds": transcript["duration_seconds"],
                    "transcription_status": TRANSCRIPTION_COMPLETED,
                    "transcription_error": None,
                    "transcribed_at": now,
                    "updated_at": now,
                }
            },
        )

        transcribed += 1

        results.append(
            TranscribeAnswerResult(
                question_id=question_id,
                status="transcribed",
                word_count=transcript["word_count"],
                flags=transcript["flags"],
            )
        )

    # The session is only fully transcribed when every question has one.
    total_with_transcript = await interview_answers_collections.count_documents(
        {"session_id": session_id, "transcription_status": TRANSCRIPTION_COMPLETED}
    )

    status = transcription_status_for(
        total_with_transcript, len(questions) or len(answers), failed
    )

    await interview_sessions_collection.update_one(
        {"_id": session["_id"]},
        {
            "$set": {
                "transcription_status": status,
                "transcribed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        },
    )

    logger.info(
        "Session %s transcription: %d done, %d skipped, %d failed (%s)",
        session_id,
        transcribed,
        skipped,
        failed,
        status,
    )

    return TranscribeSessionResponse(
        session_id=session_id,
        transcription_status=status,
        total_answers=len(answers),
        transcribed=transcribed,
        skipped=skipped,
        failed=failed,
        results=results,
    )


@router.get(
    "/sessions/{session_id}/transcripts",
    response_model=SessionTranscriptsResponse,
    dependencies=[Depends(require_permission("interviews:read"))],
)
async def get_session_transcripts(session_id: str, include_segments: bool = False):
    """Every stored transcript for a session, in question order."""
    session = await load_session_or_404(session_id)

    questions = question_by_id(session)

    answers = [
        answer
        async for answer in interview_answers_collections.find(
            {"session_id": session_id}
        )
    ]

    answers.sort(key=lambda answer: answer.get("question_index") or 0)

    transcripts = []

    for answer in answers:
        if answer.get("transcription_status") != TRANSCRIPTION_COMPLETED:
            continue

        question = questions.get(answer["question_id"], {})

        transcripts.append(
            AnswerTranscript(
                question_id=answer["question_id"],
                question_index=answer.get("question_index"),
                question_text=question.get("text"),
                competency=question.get("competency"),
                transcript=answer.get("transcript", ""),
                word_count=answer.get("transcript_word_count")
                or len((answer.get("transcript") or "").split()),
                language=answer.get("transcript_language"),
                duration_seconds=answer.get("audio_duration_seconds"),
                model=answer.get("transcript_model"),
                flags=answer.get("transcript_flags") or [],
                audio_path=answer.get("audio_path"),
                transcribed_at=answer.get("transcribed_at"),
                segments=(
                    answer.get("transcript_segments") or []
                    if include_segments
                    else []
                ),
            )
        )

    return SessionTranscriptsResponse(
        session_id=session_id,
        session_status=session["status"],
        transcription_status=session.get(
            "transcription_status", TRANSCRIPTION_PENDING
        ),
        total_questions=len(questions),
        transcribed_count=len(transcripts),
        transcripts=transcripts,
    )


# --------------------------------------------------------------------------
# Modules 15 & 16 - rubric scoring and the scorecard
# --------------------------------------------------------------------------

SCORING_PENDING = "pending"
SCORING_PARTIAL = "partial"
SCORING_COMPLETED = "completed"


async def load_rubric_for_session(session: dict) -> list[dict]:
    """The rubric for this session's job, or the default competencies."""
    job_id = str(session.get("job_id", ""))

    job = None

    if ObjectId.is_valid(job_id):
        job = await jobs_collection.find_one({"_id": ObjectId(job_id)})

    try:
        return get_rubric_for_job(job)
    except RubricError as error:
        # A job with a broken rubric must not silently fall back to a
        # different standard - that would score candidates inconsistently.
        raise HTTPException(
            status_code=400, detail=f"This job's interview rubric is unusable: {error}"
        ) from error


@router.post(
    "/sessions/{session_id}/score",
    response_model=ScoreSessionResponse,
    dependencies=[Depends(require_permission("interviews:score"))],
)
async def score_interview_session(session_id: str, force: bool = False):
    """Score every answer against the rubric and build one scorecard.

    Each question is scored for the competency it tests, with an evidence quote
    verified against the transcript. Questions with no answer or no transcript
    are reported as such rather than skipped, so the scorecard covers the whole
    interview.
    """
    session = await load_session_or_404(session_id)

    rubric = await load_rubric_for_session(session)

    questions = session["questions"]

    if not questions:
        raise HTTPException(status_code=400, detail="This session has no questions")

    answers = {
        answer["question_id"]: answer
        async for answer in interview_answers_collections.find(
            {"session_id": session_id}
        )
    }

    answer_scores = []

    for index, question in enumerate(questions):
        question_id = question["id"]

        answer = answers.get(question_id)

        competency = entry_for_competency(rubric, question.get("competency"))[
            "competency"
        ]

        base = {
            "question_id": question_id,
            "question_index": index,
            "question_text": question.get("text"),
            "competency": competency,
        }

        if not answer:
            answer_scores.append(
                {
                    **base,
                    "score": None,
                    "evidence_quote": "",
                    "quote_verified": False,
                    "reasoning": "Not scored: the candidate did not answer this question.",
                    "answers_question": False,
                    "flags": [FLAG_UNANSWERED],
                    "model": None,
                }
            )

            continue

        if answer.get("transcription_status") != TRANSCRIPTION_COMPLETED:
            answer_scores.append(
                {
                    **base,
                    "score": None,
                    "evidence_quote": "",
                    "quote_verified": False,
                    "reasoning": (
                        "Not scored: this answer has not been transcribed yet."
                    ),
                    "answers_question": None,
                    "flags": [FLAG_NOT_TRANSCRIBED],
                    "model": None,
                }
            )

            continue

        # Reuse a stored score unless asked to redo it; a model call per
        # answer is the expensive part.
        if answer.get("score_result") and not force:
            # `base` last: the current rubric decides the competency, not
            # whatever it was when this answer was first scored.
            answer_scores.append({**answer["score_result"], **base})

            continue

        result = await score_answer(
            transcript=answer.get("transcript", ""),
            question=question,
            rubric=rubric,
        )

        await interview_answers_collections.update_one(
            {"_id": answer["_id"]},
            {
                "$set": {
                    "score_result": result,
                    "scored_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        answer_scores.append({**base, **result})

    scorecard = build_scorecard(session, rubric, answer_scores)

    scored_count = scorecard["answers_scored"]

    if scored_count == 0:
        scoring_status = SCORING_PENDING
    elif scored_count < len(questions):
        scoring_status = SCORING_PARTIAL
    else:
        scoring_status = SCORING_COMPLETED

    now = datetime.utcnow()

    await interview_sessions_collection.update_one(
        {"_id": session["_id"]},
        {
            "$set": {
                "scorecard": scorecard,
                "answer_scores": answer_scores,
                "scoring_status": scoring_status,
                "scored_at": now,
                "updated_at": now,
            }
        },
    )

    logger.info(
        "Session %s scored: overall=%s, %d/%d answers, review=%s",
        session_id,
        scorecard["overall_score"],
        scored_count,
        len(questions),
        scorecard["needs_human_review"],
    )

    return ScoreSessionResponse(
        session_id=session_id,
        candidate_id=session["candidate_id"],
        job_id=str(session["job_id"]),
        scoring_status=scoring_status,
        scored_at=now,
        scorecard=Scorecard(**scorecard),
        answer_scores=[AnswerScore(**score) for score in answer_scores],
    )


@router.get(
    "/sessions/{session_id}/scorecard",
    response_model=ScorecardResponse,
    dependencies=[Depends(require_permission("interviews:read"))],
)
async def get_interview_scorecard(session_id: str):
    """The stored scorecard for a session."""
    session = await load_session_or_404(session_id)

    scorecard = session.get("scorecard")

    if not scorecard:
        raise HTTPException(
            status_code=404,
            detail=(
                "This interview has not been scored yet; "
                f"POST /interviews/sessions/{session_id}/score first"
            ),
        )

    return ScorecardResponse(
        session_id=session_id,
        candidate_id=session["candidate_id"],
        job_id=str(session["job_id"]),
        scoring_status=session.get("scoring_status", SCORING_PENDING),
        scored_at=session.get("scored_at"),
        scorecard=Scorecard(**scorecard),
        answer_scores=[
            AnswerScore(**score) for score in session.get("answer_scores") or []
        ],
    )

from pathlib import Path
import logging
from datetime import datetime
from bson import ObjectId

from fastapi import (
    File,
    Form,
    UploadFile,
)
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.db.mongodb import (
    interview_answers_collections,
    candidates_collection,
    interview_sessions_collection,
)
from app.schemas.interview import (
    InterviewSessionResponse,
    CreateInterviewSessionResponse,
    CreateInterviewSessionRequest,
    AcknowledgeIntroResponse,
    InterviewQuestion,
    UploadAnswerResponse,
)

from app.models.interview_answer import create_interview_answer_document
from app.models.interview_session import (
    STATUS_IN_PROGRESS,
    STATUS_INVITED,
)
from app.services.interview_service import (
    build_invite_url,
    create_session_for_candidate,
    invite_is_expired,
    is_eligible_for_interview,
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

    with open(file_path, "wb") as f:
        f.write(content)

    logger.info("Interview answer saved: %s", file_path)

    document = create_interview_answer_document(
        session_id=session_id,
        question_id=question_id,
        filename=filename,
        file_path=str(file_path),
        question_index=question_index,
        time_limit_seconds=questions[question_index]["time_limit_seconds"],
    )

    result = await interview_answers_collections.insert_one(document)

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


@router.get("/{session_id}/questions/{question_id}/answers")
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


@router.post("/sessions", response_model=CreateInterviewSessionResponse)
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


# Get Interview Session
@router.get("/sessions/{session_id}", response_model=InterviewSessionResponse)
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

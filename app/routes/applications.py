import logging
from pathlib import Path
from typing import Literal

from bson import ObjectId
import os

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse

from app.core.auth import get_current_user, optional_user, require_permission

from app.db.mongodb import (
    candidates_collection,
    interview_answers_collections,
    interview_sessions_collection,
    jobs_collection,
)
from app.models.candidate import create_candidate_document
from app.schemas.candidate import (
    CandidateDetailResponse,
    CandidateInterviewDetail,
    CandidateListResponse,
    CandidateResponse,
    CandidateScreeningDetail,
    CandidateSummary,
    JourneyStep,
    MyApplication,
    MyApplicationsResponse,
)
from app.services.candidate_processor import process_candidate
from app.services.notifications import KIND_NEW_APPLICATION, notify_administration
from app.services.job_lifecycle import closed_reason, is_open
from app.services.application_journey import journey_summary
from app.services.qdrant_service import get_candidate_embedding

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/applications", tags=["Applications"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/", response_model=CandidateResponse)
async def create_application(
    background_tasks: BackgroundTasks,
    job_id: str = Form(...),
    resume: UploadFile = File(...),
    applicant: dict | None = Depends(optional_user),
):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    job = await jobs_collection.find_one({"_id": ObjectId(job_id)})

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # A role that is a draft, not published yet, or past its deadline does not
    # accept applications. Refused with 409 rather than 404: the role exists,
    # it is just not open, and the reason is something the applicant can act
    # on (or wait for).
    if not is_open(job):
        raise HTTPException(status_code=409, detail=closed_reason(job))

    allowed_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    if resume.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Resume must be a PDF or DOCX file")

    file_path = UPLOAD_DIR / resume.filename

    content = await resume.read()

    with open(file_path, "wb") as file:
        file.write(content)

    candidate = create_candidate_document(
        job_id=job_id,
        resume_filename=resume.filename,
        resume_path=str(file_path),
        applicant_user_id=str(applicant["_id"]) if applicant else None,
        applicant_email=applicant.get("email") if applicant else None,
    )

    result = await candidates_collection.insert_one(candidate)

    candidate_id = str(result.inserted_id)

    background_tasks.add_task(process_candidate, candidate_id)

    # Let the hiring team know a new application has arrived to screen.
    await notify_administration(
        KIND_NEW_APPLICATION,
        f"New application — {job.get('title', 'a role')}",
        "A resume was submitted and is being processed.",
    )

    return CandidateResponse(
        id=str(result.inserted_id),
        job_id=job_id,
        resume_filename=resume.filename,
        resume_path=str(file_path),
        name=None,
        email=None,
        skills=[],
        years_of_experience=None,
        education=[],
        status="received",
    )


@router.get("/mine", response_model=MyApplicationsResponse)
async def my_applications(user: dict = Depends(get_current_user)):
    """The signed-in candidate's own applications, with where each has reached.

    Matched by the account that applied, and by the account's email as a
    fallback - a candidate who applied before signing up still sees those once
    the emails line up. Administration users have the recruiter views instead,
    so this is scoped to the caller either way.
    """
    user_id = str(user["_id"])
    email = (user.get("email") or "").lower()

    query = {
        "$or": [
            {"applicant_user_id": user_id},
            *([{"applicant_email": email}] if email else []),
            *([{"email": email}] if email else []),
        ]
    }

    applications = []

    async for candidate in candidates_collection.find(query).sort(
        [("created_at", -1)]
    ):
        job = None
        job_id = str(candidate.get("job_id", ""))
        if ObjectId.is_valid(job_id):
            job = await jobs_collection.find_one({"_id": ObjectId(job_id)})

        session = await interview_sessions_collection.find_one(
            {"candidate_id": str(candidate["_id"])}
        )

        if session:
            session = {
                **session,
                "answered_count": await interview_answers_collections.count_documents(
                    {"session_id": str(session["_id"])}
                ),
                "total_questions": len(session.get("questions") or []),
            }

        summary = journey_summary(candidate, session)

        applications.append(
            MyApplication(
                id=str(candidate["_id"]),
                job_id=job_id,
                job_title=(job or {}).get("title"),
                status=candidate.get("status", "received"),
                decision=candidate.get("decision"),
                screening_score=candidate.get("screening_score"),
                applied_at=candidate.get("created_at"),
                current_step=JourneyStep(**summary["current"]),
                completed_steps=summary["completed"],
                total_steps=summary["total"],
                steps=[JourneyStep(**step) for step in summary["steps"]],
                interview_invite_url=candidate.get("interview_invite_url"),
                interview_status=(session or {}).get("status"),
            )
        )

    return MyApplicationsResponse(
        total=len(applications), applications=applications
    )


@router.get(
    "/{candidate_id}/vector",
    dependencies=[Depends(require_permission("candidates:read"))],
)
async def get_candidate_vector(candidate_id: str):
    result = await get_candidate_embedding(candidate_id)

    if not result:
        raise HTTPException(status_code=404, detail="Candidate embedding not found")

    point = result[0]

    return {
        "candidate_id": candidate_id,
        "payload": point.payload,
        "vector_dimensions": len(point.vector),
    }


@router.get(
    "/{candidate_id}/screening",
    dependencies=[Depends(require_permission("candidates:read"))],
)
async def get_candidate_screening(
    candidate_id: str,
):

    if not ObjectId.is_valid(candidate_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid candidate ID",
        )

    candidate = await candidates_collection.find_one({"_id": ObjectId(candidate_id)})

    if not candidate:
        raise HTTPException(
            status_code=404,
            detail="Candidate not found",
        )

    if candidate.get("screening_score") is None:
        return {
            "candidate_id": candidate_id,
            "status": candidate.get(
                "status",
                "processing",
            ),
            "message": ("Screening has not completed yet"),
        }

    return {
        "candidate_id": candidate_id,
        "candidate_name": candidate.get("name"),
        "screening_score": candidate.get("screening_score"),
        "semantic_similarity": candidate.get("semantic_similarity"),
        "skill_score": candidate.get("skill_score"),
        "experience_score": candidate.get("experience_score"),
        "matched_skills": candidate.get(
            "matched_skills",
            [],
        ),
        "missing_skills": candidate.get(
            "missing_skills",
            [],
        ),
        "rationale": candidate.get("screening_rationale"),
    }


# --------------------------------------------------------------------------
# Browsing candidates
# --------------------------------------------------------------------------

# Highest-scoring first is what a recruiter wants by default; candidates still
# being processed have no score yet and sort last.
SORT_FIELDS = {
    "score": [("screening_score", -1), ("created_at", -1)],
    "recent": [("created_at", -1)],
    "name": [("name", 1)],
}


def candidate_summary(candidate: dict) -> CandidateSummary:
    return CandidateSummary(
        id=str(candidate["_id"]),
        job_id=str(candidate.get("job_id", "")),
        name=candidate.get("name"),
        email=candidate.get("email"),
        status=candidate.get("status", "received"),
        decision=candidate.get("decision"),
        screening_score=candidate.get("screening_score"),
        years_of_experience=candidate.get("years_of_experience"),
        skills_count=len(candidate.get("skills") or []),
        resume_filename=candidate.get("resume_filename"),
        interview_session_id=candidate.get("interview_session_id"),
        created_at=candidate.get("created_at"),
    )


@router.get(
    "/",
    response_model=CandidateListResponse,
    dependencies=[Depends(require_permission("candidates:read"))],
)
async def list_candidates(
    job_id: str | None = Query(
        None, description="Only candidates who applied to this job"
    ),
    status: str | None = Query(None, description="e.g. received, screened"),
    decision: str | None = Query(
        None, description="e.g. invited_to_interview, reject"
    ),
    min_score: float | None = Query(
        None, ge=0, le=100, description="Only candidates scoring at least this"
    ),
    sort: Literal["score", "recent", "name"] = "score",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List candidates, newest-scoring first.

    With no filters this is every candidate in the system. Pass `job_id` for
    the candidates of one job vacancy.
    """
    query: dict = {}

    job_title = None

    if job_id is not None:
        if not ObjectId.is_valid(job_id):
            raise HTTPException(status_code=400, detail="Invalid job_id format")

        job = await jobs_collection.find_one({"_id": ObjectId(job_id)})

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        job_title = job.get("title")

        query["job_id"] = job_id

    if status is not None:
        query["status"] = status

    if decision is not None:
        query["decision"] = decision

    if min_score is not None:
        query["screening_score"] = {"$gte": min_score}

    total = await candidates_collection.count_documents(query)

    cursor = (
        candidates_collection.find(query)
        .sort(SORT_FIELDS[sort])
        .skip(offset)
        .limit(limit)
    )

    candidates = [candidate_summary(candidate) async for candidate in cursor]

    return CandidateListResponse(
        total=total,
        count=len(candidates),
        limit=limit,
        offset=offset,
        job_id=job_id,
        job_title=job_title,
        status=status,
        decision=decision,
        sort=sort,
        candidates=candidates,
    )


@router.get(
    "/{candidate_id}",
    response_model=CandidateDetailResponse,
    dependencies=[Depends(require_permission("candidates:read"))],
)
async def get_candidate(candidate_id: str):
    """Everything known about one candidate: resume data, screening, interview."""
    if not ObjectId.is_valid(candidate_id):
        raise HTTPException(status_code=400, detail="Invalid candidate ID")

    candidate = await candidates_collection.find_one(
        {"_id": ObjectId(candidate_id)}
    )

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    job_id = str(candidate.get("job_id", ""))

    job = None

    if ObjectId.is_valid(job_id):
        job = await jobs_collection.find_one({"_id": ObjectId(job_id)})

    # The interview lives in its own collection; look it up by candidate so a
    # candidate invited before `interview_session_id` was stored still resolves.
    session = await interview_sessions_collection.find_one(
        {"candidate_id": candidate_id}
    )

    interview = CandidateInterviewDetail()

    if session:
        answered_count = await interview_answers_collections.count_documents(
            {"session_id": str(session["_id"])}
        )

        interview = CandidateInterviewDetail(
            session_id=str(session["_id"]),
            status=session.get("status"),
            invite_url=candidate.get("interview_invite_url"),
            invite_expires_at=session.get("invite_expires_at"),
            total_questions=len(session.get("questions") or []),
            answered_count=answered_count,
            transcription_status=session.get("transcription_status"),
            submitted_at=session.get("submitted_at"),
        )

    return CandidateDetailResponse(
        id=candidate_id,
        job_id=job_id,
        job_title=(job or {}).get("title"),
        name=candidate.get("name"),
        email=candidate.get("email"),
        status=candidate.get("status", "received"),
        decision=candidate.get("decision"),
        decision_message=candidate.get("decision_message"),
        years_of_experience=candidate.get("years_of_experience"),
        skills=candidate.get("skills") or [],
        education=candidate.get("education") or [],
        resume_filename=candidate.get("resume_filename"),
        resume_path=candidate.get("resume_path"),
        email_status=candidate.get("email_status"),
        email_sent_at=candidate.get("email_sent_at"),
        email_error=candidate.get("email_error"),
        created_at=candidate.get("created_at"),
        updated_at=candidate.get("updated_at"),
        screening=CandidateScreeningDetail(
            screening_score=candidate.get("screening_score"),
            semantic_similarity=candidate.get("semantic_similarity"),
            skill_score=candidate.get("skill_score"),
            experience_score=candidate.get("experience_score"),
            matched_skills=candidate.get("matched_skills") or [],
            missing_skills=candidate.get("missing_skills") or [],
            rationale=candidate.get("screening_rationale"),
        ),
        interview=interview,
    )


@router.get(
    "/{candidate_id}/resume",
    dependencies=[Depends(require_permission("candidates:read"))],
)
async def get_candidate_resume(candidate_id: str):
    """Download a candidate's uploaded CV, so a reviewer can read the original.

    Restricted to candidates:read (the hiring team and the superadmin); a
    candidate cannot pull another applicant's resume.
    """
    if not ObjectId.is_valid(candidate_id):
        raise HTTPException(status_code=400, detail="Invalid candidate ID")

    candidate = await candidates_collection.find_one(
        {"_id": ObjectId(candidate_id)}
    )

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    resume_path = candidate.get("resume_path")

    if not resume_path or not os.path.exists(resume_path):
        raise HTTPException(status_code=404, detail="No resume on file")

    return FileResponse(
        resume_path,
        filename=candidate.get("resume_filename") or "resume",
    )

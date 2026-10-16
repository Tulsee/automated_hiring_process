import logging
from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from app.db.mongodb import jobs_collection
from app.models.job import create_job_document
from app.schemas.job import JobCreate, JobResponse, JobUpdate
from app.services.job_lifecycle import (
    SETTABLE_STATUSES,
    STATE_OPEN,
    ScheduleError,
    closed_reason,
    job_state,
    to_naive_utc,
    validate_schedule,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


def job_response(job: dict) -> JobResponse:
    """One job, with its derived state attached."""
    state = job_state(job)

    return JobResponse(
        id=str(job["_id"]),
        title=job["title"],
        description=job.get("description", ""),
        required_skills=job.get("required_skills", []),
        minimum_experience=job.get("minimum_experience", 0),
        interview_questions=job.get("interview_questions", []),
        status=job.get("status") or "published",
        publish_at=job.get("publish_at"),
        deadline=job.get("deadline"),
        state=state,
        state_reason=None if state == STATE_OPEN else closed_reason(job),
        created_at=job.get("created_at"),
        updated_at=job.get("updated_at"),
    )


@router.post("/", response_model=JobResponse)
async def create_job(job: JobCreate):
    if job.status not in SETTABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(SETTABLE_STATUSES)}",
        )

    try:
        validate_schedule(job.publish_at, job.deadline)
    except ScheduleError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    job_document = create_job_document(
        title=job.title,
        description=job.description,
        required_skills=job.required_skills,
        minimum_experience=job.minimum_experience,
        interview_questions=[
            question.model_dump(exclude_none=True)
            for question in job.interview_questions
        ],
        status=job.status,
        publish_at=to_naive_utc(job.publish_at),
        deadline=to_naive_utc(job.deadline),
    )

    result = await jobs_collection.insert_one(job_document)

    job_document["_id"] = result.inserted_id

    logger.info("Job created: %s (%s)", result.inserted_id, job_state(job_document))

    return job_response(job_document)


@router.get("/", response_model=list[JobResponse])
async def list_jobs(
    open_only: bool = Query(
        False,
        description=(
            "Only roles accepting applications right now. The candidate-facing "
            "portal passes this; a recruiter wants drafts and closed roles too."
        ),
    ),
    status: str | None = Query(
        None,
        description="Filter by the recruiter's status: draft, published or closed",
    ),
):
    jobs = []

    query: dict = {}

    if status is not None:
        query["status"] = status

    async for job in jobs_collection.find(query):
        # Filtered in Python rather than Mongo: whether a job is open depends
        # on the clock as well as its fields, and that rule lives in one place.
        if open_only and job_state(job) != STATE_OPEN:
            continue

        jobs.append(job_response(job))

    return jobs


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    job = await jobs_collection.find_one({"_id": ObjectId(job_id)})

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job_response(job)


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(job_id: str, changes: JobUpdate):
    """Change a job's content or its application window.

    Only the fields sent are touched, so a deadline can be moved without
    resending the questions. An explicit `null` clears a date; omitting the
    field leaves it as it is.
    """
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    job = await jobs_collection.find_one({"_id": ObjectId(job_id)})

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    updates = changes.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(status_code=400, detail="No changes were sent")

    if "status" in updates and updates["status"] not in SETTABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(SETTABLE_STATUSES)}",
        )

    if "interview_questions" in updates:
        # Drop keys the client left empty so the backend defaults still apply.
        updates["interview_questions"] = [
            {key: value for key, value in question.items() if value is not None}
            for question in updates["interview_questions"] or []
        ]

    for field in ("publish_at", "deadline"):
        if field in updates:
            updates[field] = to_naive_utc(updates[field])

    # Validate the window the job will have *after* this change, not only the
    # fields that happen to be in this request.
    try:
        validate_schedule(
            updates.get("publish_at", job.get("publish_at")),
            updates.get("deadline", job.get("deadline")),
        )
    except ScheduleError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    updates["updated_at"] = datetime.utcnow()

    await jobs_collection.update_one({"_id": ObjectId(job_id)}, {"$set": updates})

    updated = await jobs_collection.find_one({"_id": ObjectId(job_id)})

    logger.info(
        "Job %s updated (%s): %s",
        job_id,
        job_state(updated),
        ", ".join(sorted(key for key in updates if key != "updated_at")),
    )

    return job_response(updated)

from pathlib import Path

from bson import ObjectId
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, BackgroundTasks

from app.db.mongodb import candidates_collection, jobs_collection
from app.models.candidate import create_candidate_document
from app.schemas.candidate import CandidateResponse
from app.services.candidate_processor import process_candidate
from app.services.qdrant_service import get_candidate_embedding

router = APIRouter(prefix="/applications", tags=["Applications"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/", response_model=CandidateResponse)
async def create_application(
    background_tasks: BackgroundTasks,
    job_id: str = Form(...),
    resume: UploadFile = File(...),
):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    job = await jobs_collection.find_one({"_id": ObjectId(job_id)})

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

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
    )

    result = await candidates_collection.insert_one(candidate)

    candidate_id = str(result.inserted_id)

    background_tasks.add_task(process_candidate, candidate_id)

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


@router.get("/{candidate_id}/vector")
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

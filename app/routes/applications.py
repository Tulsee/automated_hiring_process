from pathlib import Path

from bson import ObjectId
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.db.mongodb import candidates_collection, jobs_collection
from app.models.candidate import create_candidate_document
from app.schemas.candidate import CandidateResponse

router = APIRouter(prefix="/applications", tags=["Applications"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/", response_model=CandidateResponse)
async def create_application(
    job_id: str = Form(...),
    resume: UploadFile = File(...),
    name: str = Form(...),
    email: str = Form(...),
):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    job = await jobs_collection.find_one({"_id": ObjectId(job_id)})

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if resume.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Resume must be a PDF file")

    file_path = UPLOAD_DIR / resume.filename

    content = await resume.read()

    with open(file_path, "wb") as file:
        file.write(content)

    candidate = create_candidate_document(
        job_id=job_id,
        resume_filename=resume.filename,
        resume_path=str(file_path),
        name=name,
        email=email,
    )

    result = await candidates_collection.insert_one(candidate)

    return CandidateResponse(
        id=str(result.inserted_id),
        job_id=job_id,
        resume_filename=resume.filename,
        resume_path=str(file_path),
        status=candidate["status"],
    )

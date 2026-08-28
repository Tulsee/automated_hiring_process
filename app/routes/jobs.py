from fastapi import APIRouter

from app.db.mongodb import jobs_collection
from app.models.job import create_job_document
from app.schemas.job import JobCreate, JobResponse

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


@router.post("/", response_model=JobResponse)
async def create_job(job: JobCreate):

    job_document = create_job_document(
        title=job.title,
        description=job.description,
        required_skills=job.required_skills,
        minimum_experience=job.minimum_experience,
    )
    result = await jobs_collection.insert_one(job_document)

    return JobResponse(id=str(result.inserted_id), **job.model_dump())


@router.get("/", response_model=list[JobResponse])
async def list_jobs():

    jobs = []

    cursor = jobs_collection.find()

    async for job in cursor:
        jobs.append(
            JobResponse(
                id=str(job["_id"]),
                title=job["title"],
                description=job["description"],
                required_skills=job["required_skills"],
            )
        )

    return jobs

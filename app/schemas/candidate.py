from pydantic import BaseModel, Field


class CandidateCreate(BaseModel):
    id: str = Field(..., example="64b8f1c2e4b0f5a1c2d3e4f5")
    job_id: str = Field(..., example="64b8f1c2e4b0f5a1c2d3e4f5")
    name: str = Field(..., example="John Doe")
    email: str = Field(..., example="john.doe@example.com")
    resume_filename: str = Field(..., example="resume.pdf")
    resume_path: str = Field(..., example="/path/to/resume.pdf")
    status: str = Field(..., example="received")


class CandidateResponse(BaseModel):
    id: str = Field(..., example="64b8f1c2e4b0f5a1c2d3e4f5")
    job_id: str = Field(..., example="64b8f1c2e4b0f5a1c2d3e4f5")
    resume_filename: str = Field(..., example="resume.pdf")
    resume_path: str = Field(..., example="/path/to/resume.pdf")
    status: str = Field(..., example="received")

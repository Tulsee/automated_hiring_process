from datetime import datetime

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


class Education(BaseModel):
    degree: str | None = None
    institution: str | None = None
    year: str | None = None


class CandidateExtraction(BaseModel):
    name: str | None = None
    email: str | None = None
    skills: list[str] = Field(default_factory=list)
    years_of_experience: float | None = None
    education: list[Education] = Field(default_factory=list)


class CandidateSummary(BaseModel):
    """One row in a candidate list - enough to scan and rank, not the detail."""

    id: str
    job_id: str
    name: str | None = None
    email: str | None = None
    status: str
    decision: str | None = None
    screening_score: float | None = None
    years_of_experience: float | None = None
    skills_count: int = 0
    resume_filename: str | None = None
    interview_session_id: str | None = None
    created_at: datetime | None = None


class CandidateListResponse(BaseModel):
    """A page of candidates, with the filters that produced it."""

    total: int
    count: int
    limit: int
    offset: int
    job_id: str | None = None
    job_title: str | None = None
    status: str | None = None
    decision: str | None = None
    sort: str
    candidates: list[CandidateSummary] = []


class CandidateScreeningDetail(BaseModel):
    """The screening breakdown, so a score can be explained."""

    screening_score: float | None = None
    semantic_similarity: float | None = None
    skill_score: float | None = None
    experience_score: float | None = None
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    rationale: str | None = None


class CandidateInterviewDetail(BaseModel):
    """Where the candidate has got to in the interview, if invited."""

    session_id: str | None = None
    status: str | None = None
    invite_url: str | None = None
    invite_expires_at: datetime | None = None
    total_questions: int = 0
    answered_count: int = 0
    transcription_status: str | None = None
    submitted_at: datetime | None = None


class CandidateDetailResponse(BaseModel):
    """Everything known about one candidate, in one place."""

    id: str
    job_id: str
    job_title: str | None = None
    name: str | None = None
    email: str | None = None
    status: str
    decision: str | None = None
    decision_message: str | None = None
    years_of_experience: float | None = None
    skills: list[str] = []
    education: list[Education] = []
    resume_filename: str | None = None
    resume_path: str | None = None
    email_status: str | None = None
    email_sent_at: datetime | None = None
    email_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    screening: CandidateScreeningDetail = Field(
        default_factory=CandidateScreeningDetail
    )
    interview: CandidateInterviewDetail = Field(
        default_factory=CandidateInterviewDetail
    )

from pydantic import BaseModel, Field


class JobInterviewQuestion(BaseModel):
    """One question of a job's fixed interview template."""

    id: str | None = None
    text: str = Field(..., example="How would you design a scalable REST API?")
    competency: str | None = Field(None, example="system_design")
    time_limit_seconds: int | None = Field(None, example=90)


class JobCreate(BaseModel):
    title: str = Field(..., example="Software Engineer")
    description: str = Field(
        ..., example="Responsible for developing software applications."
    )
    required_skills: list[str] = Field(default_factory=list)
    minimum_experience: float = 0
    interview_questions: list[JobInterviewQuestion] = Field(default_factory=list)


class JobResponse(JobCreate):
    id: str = Field(..., example="64b8f1c2e4b0f5a1c2d3e4f5")

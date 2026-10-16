from datetime import datetime

from pydantic import BaseModel, Field

from app.services.job_lifecycle import STATUS_PUBLISHED


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

    # draft | published | closed. A draft is never visible to applicants.
    status: str = STATUS_PUBLISHED

    # When the role becomes visible, and when it stops accepting applications.
    # Null means "immediately" and "no closing date".
    publish_at: datetime | None = Field(None, example="2026-11-01T09:00:00")
    deadline: datetime | None = Field(None, example="2026-12-01T23:59:00")


class JobUpdate(BaseModel):
    """A partial update.

    Every field is optional, and *unset* is distinguished from *null*: sending
    `{"deadline": null}` clears the deadline, while omitting it leaves the
    existing one alone. The route relies on `exclude_unset` for that.
    """

    title: str | None = None
    description: str | None = None
    required_skills: list[str] | None = None
    minimum_experience: float | None = None
    interview_questions: list[JobInterviewQuestion] | None = None
    status: str | None = None
    publish_at: datetime | None = None
    deadline: datetime | None = None


class JobResponse(JobCreate):
    id: str = Field(..., example="64b8f1c2e4b0f5a1c2d3e4f5")

    # Derived, never stored: draft | scheduled | open | expired | closed.
    state: str = Field(STATUS_PUBLISHED, example="open")

    # Why applications are refused, when they are.
    state_reason: str | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None

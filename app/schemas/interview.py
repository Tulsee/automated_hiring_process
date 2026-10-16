from datetime import datetime

from pydantic import BaseModel


class InterviewQuestion(BaseModel):
    id: str
    text: str
    competency: str = "general"
    time_limit_seconds: int


class CreateInterviewSessionRequest(BaseModel):
    candidate_id: str


class InterviewSessionResponse(BaseModel):
    id: str
    candidate_id: str
    job_id: str
    current_question_index: int
    total_questions: int
    total_time_seconds: int
    status: str
    questions: list[InterviewQuestion] = []
    question: InterviewQuestion | None = None
    intro_acknowledged: bool = False
    invite_expires_at: datetime | None = None


class CreateInterviewSessionResponse(InterviewSessionResponse):
    """Adds the one-time invite link the candidate is sent."""

    invite_token: str
    invite_url: str


class AcknowledgeIntroResponse(BaseModel):
    """Result of accepting the intro screen, which unlocks recording."""

    session_id: str
    status: str
    intro_acknowledged: bool
    total_questions: int
    total_time_seconds: int
    question: InterviewQuestion | None = None


class UploadAnswerResponse(BaseModel):
    """Result of uploading the video for a single question."""

    id: str
    session_id: str
    question_id: str
    filename: str
    status: str
    answered_count: int
    total_questions: int
    session_status: str
    next_question: InterviewQuestion | None = None

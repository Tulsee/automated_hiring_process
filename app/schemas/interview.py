from pydantic import BaseModel


class InterviewQuestion(BaseModel):
    id: str
    text: str
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

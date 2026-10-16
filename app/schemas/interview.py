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


class TranscriptSegment(BaseModel):
    """One timed chunk of speech, kept so a transcript can be spot-checked."""

    start: float
    end: float
    text: str
    avg_logprob: float | None = None
    no_speech_prob: float | None = None


class AnswerTranscript(BaseModel):
    """The transcript of one answered question."""

    question_id: str
    question_index: int | None = None
    question_text: str | None = None
    competency: str | None = None
    transcript: str
    word_count: int
    language: str | None = None
    duration_seconds: float | None = None
    model: str | None = None
    flags: list[str] = []
    audio_path: str | None = None
    transcribed_at: datetime | None = None
    segments: list[TranscriptSegment] = []


class TranscribeAnswerResult(BaseModel):
    """What happened to one answer during a transcription run."""

    question_id: str
    status: str
    word_count: int | None = None
    flags: list[str] = []
    error: str | None = None


class TranscribeSessionResponse(BaseModel):
    session_id: str
    transcription_status: str
    total_answers: int
    transcribed: int
    skipped: int
    failed: int
    results: list[TranscribeAnswerResult] = []


class SessionTranscriptsResponse(BaseModel):
    session_id: str
    session_status: str
    transcription_status: str
    total_questions: int
    transcribed_count: int
    transcripts: list[AnswerTranscript] = []

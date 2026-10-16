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


# --------------------------------------------------------------------------
# Modules 15 & 16 - rubric scoring and the scorecard
# --------------------------------------------------------------------------


class RubricCompetency(BaseModel):
    """One competency of the rubric, reported with the scorecard."""

    competency: str
    name: str
    weight: float
    descriptors: dict[str, str] = {}


class AnswerScore(BaseModel):
    """The rubric result for one answer, with the quote that supports it."""

    question_id: str
    question_index: int | None = None
    question_text: str | None = None
    competency: str
    score: int | None = None
    evidence_quote: str = ""
    quote_verified: bool = False
    reasoning: str = ""
    answers_question: bool | None = None
    flags: list[str] = []
    model: str | None = None


class CompetencyEvidence(BaseModel):
    question_id: str | None = None
    score: int | None = None
    quote: str = ""
    quote_verified: bool = False
    reasoning: str = ""


class CompetencyScore(BaseModel):
    """An aggregated score for one competency."""

    competency: str
    name: str
    weight: float
    score: float | None = None
    percent: float | None = None
    answers_scored: int = 0
    answers_total: int = 0
    evidence: list[CompetencyEvidence] = []
    flags: list[str] = []


class ScoreWeighting(BaseModel):
    """How the overall score was computed, so it can be recomputed by hand."""

    method: str
    competencies_used: int
    competencies_total: int
    weights: dict[str, float] = {}
    excluded: list[str] = []
    note: str | None = None


class ReviewItem(BaseModel):
    question_id: str | None = None
    competency: str
    flags: list[str] = []


class ScoreScale(BaseModel):
    min: int
    max: int


class Scorecard(BaseModel):
    """One interview's scores, evidence and review flags."""

    overall_score: float | None = None
    overall_percent: float | None = None
    scale: ScoreScale
    questions_total: int = 0
    answers_scored: int = 0
    competency_scores: list[CompetencyScore] = []
    weighting: ScoreWeighting
    flags: list[str] = []
    needs_human_review: bool = False
    review_items: list[ReviewItem] = []
    rubric: list[RubricCompetency] = []


class ScoreSessionResponse(BaseModel):
    """Result of scoring a session: the scorecard plus per-answer detail."""

    session_id: str
    candidate_id: str
    job_id: str
    scoring_status: str
    scored_at: datetime | None = None
    scorecard: Scorecard
    answer_scores: list[AnswerScore] = []


class ScorecardResponse(ScoreSessionResponse):
    """The stored scorecard for a session."""


class InterviewSessionSummary(BaseModel):
    """One row in a session list: where this interview has got to."""

    id: str
    candidate_id: str
    candidate_name: str | None = None
    job_id: str
    job_title: str | None = None
    status: str
    total_questions: int = 0
    answered_count: int = 0
    transcription_status: str | None = None
    scoring_status: str | None = None
    overall_score: float | None = None
    needs_human_review: bool | None = None
    invite_expires_at: datetime | None = None
    created_at: datetime | None = None
    submitted_at: datetime | None = None


class InterviewSessionListResponse(BaseModel):
    total: int
    count: int
    limit: int
    offset: int
    status: str | None = None
    candidate_id: str | None = None
    job_id: str | None = None
    sessions: list[InterviewSessionSummary] = []

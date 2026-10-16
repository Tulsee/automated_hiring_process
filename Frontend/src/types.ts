/**
 * Types mirroring the FastAPI response schemas.
 *
 * Kept hand-written rather than generated so the shapes the UI actually
 * depends on are visible in one place; each block names its endpoint.
 */

/* ---------------------------------------------------------------- jobs */

export interface JobInterviewQuestion {
  id: string | null;
  text: string;
  competency: string | null;
  time_limit_seconds: number | null;
}

/** GET /jobs/ and POST /jobs/ */
export interface Job {
  id: string;
  title: string;
  description: string;
  required_skills: string[];
  minimum_experience: number;
  interview_questions: JobInterviewQuestion[];
}

export interface JobDraft {
  title: string;
  description: string;
  required_skills: string[];
  minimum_experience: number;
  /** Omit or leave empty to use the backend's default template. */
  interview_questions?: {
    text: string;
    competency: string;
    time_limit_seconds: number;
  }[];
}

/* ---------------------------------------------------------- candidates */

/** A row of GET /applications/ */
export interface CandidateSummary {
  id: string;
  job_id: string;
  name: string | null;
  email: string | null;
  status: string;
  decision: string | null;
  screening_score: number | null;
  years_of_experience: number | null;
  skills_count: number;
  resume_filename: string | null;
  interview_session_id: string | null;
  created_at: string | null;
}

/** GET /applications/ */
export interface CandidateList {
  total: number;
  count: number;
  limit: number;
  offset: number;
  job_id: string | null;
  job_title: string | null;
  status: string | null;
  decision: string | null;
  sort: string;
  candidates: CandidateSummary[];
}

export interface Education {
  degree: string | null;
  institution: string | null;
  year: string | null;
}

export interface CandidateScreening {
  screening_score: number | null;
  semantic_similarity: number | null;
  skill_score: number | null;
  experience_score: number | null;
  matched_skills: string[];
  missing_skills: string[];
  rationale: string | null;
}

export interface CandidateInterview {
  session_id: string | null;
  status: string | null;
  invite_url: string | null;
  invite_expires_at: string | null;
  total_questions: number;
  answered_count: number;
  transcription_status: string | null;
  submitted_at: string | null;
}

/** GET /applications/{candidate_id} */
export interface CandidateDetail {
  id: string;
  job_id: string;
  job_title: string | null;
  name: string | null;
  email: string | null;
  status: string;
  decision: string | null;
  decision_message: string | null;
  years_of_experience: number | null;
  skills: string[];
  education: Education[];
  resume_filename: string | null;
  resume_path: string | null;
  email_status: string | null;
  email_sent_at: string | null;
  email_error: string | null;
  created_at: string | null;
  updated_at: string | null;
  screening: CandidateScreening;
  interview: CandidateInterview;
}

/* ---------------------------------------------------------- interviews */

export type SessionStatus = "invited" | "in_progress" | "submitted";

/** A row of GET /interviews/sessions */
export interface SessionSummary {
  id: string;
  candidate_id: string;
  candidate_name: string | null;
  job_id: string;
  job_title: string | null;
  status: SessionStatus | string;
  total_questions: number;
  answered_count: number;
  transcription_status: string | null;
  scoring_status: string | null;
  overall_score: number | null;
  needs_human_review: boolean | null;
  invite_expires_at: string | null;
  created_at: string | null;
  submitted_at: string | null;
}

/** GET /interviews/sessions */
export interface SessionList {
  total: number;
  count: number;
  limit: number;
  offset: number;
  sessions: SessionSummary[];
}

export interface InterviewQuestion {
  id: string;
  text: string;
  competency: string;
  time_limit_seconds: number;
}

/** GET /interviews/sessions/{id} */
export interface InterviewSession {
  id: string;
  candidate_id: string;
  job_id: string;
  current_question_index: number;
  total_questions: number;
  total_time_seconds: number;
  status: string;
  questions: InterviewQuestion[];
  question: InterviewQuestion | null;
  intro_acknowledged: boolean;
  invite_expires_at: string | null;
}

/** POST /interviews/sessions */
export interface CreatedSession extends InterviewSession {
  invite_token: string;
  invite_url: string;
}

/* --------------------------------------------------------- transcripts */

export interface AnswerTranscript {
  question_id: string;
  question_index: number | null;
  question_text: string | null;
  competency: string | null;
  transcript: string;
  word_count: number;
  language: string | null;
  duration_seconds: number | null;
  model: string | null;
  flags: string[];
  audio_path: string | null;
  transcribed_at: string | null;
}

/** GET /interviews/sessions/{id}/transcripts */
export interface SessionTranscripts {
  session_id: string;
  session_status: string;
  transcription_status: string;
  total_questions: number;
  transcribed_count: number;
  transcripts: AnswerTranscript[];
}

/** POST /interviews/sessions/{id}/transcribe */
export interface TranscribeResult {
  session_id: string;
  transcription_status: string;
  total_answers: number;
  transcribed: number;
  skipped: number;
  failed: number;
  results: {
    question_id: string;
    status: string;
    word_count: number | null;
    flags: string[];
    error: string | null;
  }[];
}

/* ----------------------------------------------------------- scorecard */

export interface RubricCompetency {
  competency: string;
  name: string;
  weight: number;
  descriptors: Record<string, string>;
}

export interface CompetencyEvidence {
  question_id: string | null;
  score: number | null;
  quote: string;
  quote_verified: boolean;
  reasoning: string;
}

export interface CompetencyScore {
  competency: string;
  name: string;
  weight: number;
  score: number | null;
  percent: number | null;
  answers_scored: number;
  answers_total: number;
  evidence: CompetencyEvidence[];
  flags: string[];
}

export interface ScoreWeighting {
  method: string;
  competencies_used: number;
  competencies_total: number;
  weights: Record<string, number>;
  excluded: string[];
  note: string | null;
}

export interface AnswerScore {
  question_id: string;
  question_index: number | null;
  question_text: string | null;
  competency: string;
  score: number | null;
  evidence_quote: string;
  quote_verified: boolean;
  reasoning: string;
  answers_question: boolean | null;
  flags: string[];
  model: string | null;
}

export interface Scorecard {
  overall_score: number | null;
  overall_percent: number | null;
  scale: { min: number; max: number };
  questions_total: number;
  answers_scored: number;
  competency_scores: CompetencyScore[];
  weighting: ScoreWeighting;
  flags: string[];
  needs_human_review: boolean;
  review_items: {
    question_id: string | null;
    competency: string;
    flags: string[];
  }[];
  rubric: RubricCompetency[];
}

/** GET /interviews/sessions/{id}/scorecard and POST .../score */
export interface ScorecardResponse {
  session_id: string;
  candidate_id: string;
  job_id: string;
  scoring_status: string;
  scored_at: string | null;
  scorecard: Scorecard;
  answer_scores: AnswerScore[];
}

/** POST /hiring/candidates/{candidate_id}/screen */
export interface ScreeningDecision {
  candidate_id: string;
  decision: string;
  screening_score: number | null;
  rationale: string | null;
  message: string | null;
}

/**
 * GET /applications/{candidate_id}/screening
 *
 * Two shapes from one endpoint: the full breakdown once screening has run, or
 * a status note while it has not. `screening_score` tells them apart.
 */
export interface ScreeningComplete {
  candidate_id: string;
  candidate_name: string | null;
  screening_score: number;
  semantic_similarity: number | null;
  skill_score: number | null;
  experience_score: number | null;
  matched_skills: string[];
  missing_skills: string[];
  rationale: string | null;
}

export interface ScreeningPending {
  candidate_id: string;
  status: string;
  message: string;
}

export type CandidateScreeningResult = ScreeningComplete | ScreeningPending;

export function screeningIsComplete(
  result: CandidateScreeningResult,
): result is ScreeningComplete {
  return "screening_score" in result;
}

/** GET /applications/{candidate_id}/vector */
export interface CandidateVector {
  candidate_id: string;
  /** What was stored alongside the embedding in Qdrant. */
  payload: Record<string, unknown>;
  vector_dimensions: number;
}

/** POST /interviews/invite/{token}/acknowledge */
export interface AcknowledgeIntroResponse {
  session_id: string;
  status: string;
  intro_acknowledged: boolean;
  total_questions: number;
  total_time_seconds: number;
  question: InterviewQuestion | null;
}

/** POST /interviews/answers */
export interface UploadAnswerResult {
  id: string;
  session_id: string;
  question_id: string;
  filename: string;
  status: string;
  answered_count: number;
  total_questions: number;
  session_status: string;
  next_question: InterviewQuestion | null;
}

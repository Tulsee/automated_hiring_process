/**
 * Thin fetch wrapper around the FastAPI backend.
 *
 * Requests go to relative paths so the Vite dev proxy forwards them to
 * uvicorn, and a production build served by FastAPI itself needs no change
 * and no CORS.
 */

import type {
  AcknowledgeIntroResponse,
  CandidateDetail,
  CandidateList,
  CandidateScreeningResult,
  CandidateVector,
  CreatedSession,
  Job,
  JobDraft,
  ScreeningDecision,
  InterviewSession,
  ScorecardResponse,
  SessionList,
  UploadAnswerResult,
  SessionTranscripts,
  TranscribeResult,
} from "../types";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** FastAPI reports errors as {detail: string} or a validation error array. */
function readDetail(body: unknown, fallback: string): string {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;

    if (typeof detail === "string") return detail;

    if (Array.isArray(detail)) {
      const first = detail[0] as { msg?: string; loc?: unknown[] } | undefined;

      if (first?.msg) {
        const field = Array.isArray(first.loc) ? first.loc.at(-1) : undefined;
        return field ? `${String(field)}: ${first.msg}` : first.msg;
      }
    }
  }

  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(path, init);
  } catch {
    // A network-level failure usually means the API is not running, which is
    // the single most common thing to get wrong in local development.
    throw new ApiError(
      "Could not reach the API. Is the FastAPI server running?",
      0,
    );
  }

  if (!response.ok) {
    let body: unknown = null;

    try {
      body = await response.json();
    } catch {
      /* a non-JSON error body is fine to ignore */
    }

    throw new ApiError(
      readDetail(body, `Request failed (${response.status})`),
      response.status,
    );
  }

  if (response.status === 204) return undefined as T;

  return (await response.json()) as T;
}

function query(params: Record<string, string | number | undefined | null>) {
  const search = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }

  const serialised = search.toString();

  return serialised ? `?${serialised}` : "";
}

export interface CandidateFilters {
  job_id?: string;
  status?: string;
  decision?: string;
  min_score?: number;
  sort?: "score" | "recent" | "name";
  limit?: number;
  offset?: number;
}

export const api = {
  /* jobs */
  listJobs: () => request<Job[]>("/jobs/"),

  createJob: (draft: JobDraft) =>
    request<Job>("/jobs/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(draft),
    }),

  /* candidates */
  listCandidates: (filters: CandidateFilters = {}) =>
    request<CandidateList>(`/applications/${query({ ...filters })}`),

  getCandidate: (candidateId: string) =>
    request<CandidateDetail>(`/applications/${candidateId}`),

  /** Resume upload is multipart; the browser sets the boundary itself. */
  applyToJob: (jobId: string, resume: File) => {
    const form = new FormData();
    form.append("job_id", jobId);
    form.append("resume", resume);

    return request<{ id: string; status: string }>("/applications/", {
      method: "POST",
      body: form,
    });
  },

  /**
   * The screening breakdown on its own.
   *
   * The detail endpoint already nests this, but only this one distinguishes
   * "not screened yet" from "screened with no score": it returns a status note
   * while processing is still running or has failed.
   */
  getCandidateScreening: (candidateId: string) =>
    request<CandidateScreeningResult>(
      `/applications/${candidateId}/screening`,
    ),

  /**
   * The stored embedding's metadata.
   *
   * A diagnostic: it reports the vector's dimensions and the payload kept
   * beside it in Qdrant, which is how you check a candidate was actually
   * indexed. 404 means no embedding exists for them.
   */
  getCandidateVector: (candidateId: string) =>
    request<CandidateVector>(`/applications/${candidateId}/vector`),

  /**
   * Run the screening decision for a candidate.
   *
   * This is the step that turns a *scored* candidate into a *decided* one: the
   * hiring graph sets the decision, emails the candidate, and creates their
   * interview session. Uploading a resume only computes the score, so without
   * this a candidate never progresses.
   *
   * It calls an LLM and sends mail, so it is slow — expect tens of seconds.
   */
  screenCandidate: (candidateId: string) =>
    request<ScreeningDecision>(
      `/hiring/candidates/${candidateId}/screen`,
      { method: "POST" },
    ),

  /** Liveness, for telling "no candidates" apart from "API is down". */
  health: () => request<{ status: string }>("/health"),

  /* interviews */
  listSessions: (
    filters: {
      status?: string;
      candidate_id?: string;
      job_id?: string;
      limit?: number;
    } = {},
  ) => request<SessionList>(`/interviews/sessions${query({ ...filters })}`),

  createSession: (candidateId: string) =>
    request<CreatedSession>("/interviews/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidate_id: candidateId }),
    }),

  /* the applicant's interview flow */

  /** Resolve an invite token to its session. Does not start anything. */
  getInvite: (token: string) =>
    request<InterviewSession>(`/interviews/invite/${token}`),

  /** Accept the intro, which is what makes the session recordable. */
  acknowledgeIntro: (token: string) =>
    request<AcknowledgeIntroResponse>(
      `/interviews/invite/${token}/acknowledge`,
      { method: "POST" },
    ),

  /**
   * Upload the recording for one question.
   *
   * Multipart, with the browser setting the boundary. The blob's own MIME type
   * is passed through so the server stores the right extension.
   */
  uploadAnswer: (sessionId: string, questionId: string, video: Blob) => {
    const form = new FormData();
    form.append("session_id", sessionId);
    form.append("question_id", questionId);
    form.append("answer", video, `${sessionId}_${questionId}.webm`);

    return request<UploadAnswerResult>("/interviews/answers", {
      method: "POST",
      body: form,
    });
  },

  getTranscripts: (sessionId: string) =>
    request<SessionTranscripts>(
      `/interviews/sessions/${sessionId}/transcripts`,
    ),

  transcribe: (sessionId: string) =>
    request<TranscribeResult>(
      `/interviews/sessions/${sessionId}/transcribe`,
      { method: "POST" },
    ),

  getScorecard: (sessionId: string) =>
    request<ScorecardResponse>(`/interviews/sessions/${sessionId}/scorecard`),

  score: (sessionId: string) =>
    request<ScorecardResponse>(`/interviews/sessions/${sessionId}/score`, {
      method: "POST",
    }),

  /** The stored video for one answer, for the review player. */
  answerVideoUrl: (sessionId: string, questionId: string) =>
    `/interviews/${sessionId}/questions/${questionId}/answers`,
};

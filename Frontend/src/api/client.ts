/**
 * Thin fetch wrapper around the FastAPI backend.
 *
 * Requests go to relative paths so the Vite dev proxy forwards them to
 * uvicorn, and a production build served by FastAPI itself needs no change
 * and no CORS.
 */

import type {
  AcknowledgeIntroResponse,
  AuthResult,
  AuthUser,
  CandidateDetail,
  CandidateList,
  CandidateScreeningResult,
  CandidateVector,
  CreatedSession,
  Job,
  JobDraft,
  JobUpdate,
  MyApplicationsResponse,
  PermissionInfo,
  Role,
  RoleDraft,
  CreateUserDraft,
  UpdateUserDraft,
  ScreeningDecision,
  DecisionReviewResponse,
  DecisionRequest,
  DecisionResult,
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

/**
 * The current bearer token, held in a module variable rather than passed to
 * every call.
 *
 * It is set from the auth context on login and on load (from localStorage).
 * `onUnauthorized` lets the context react to a token the server rejects - an
 * expired session - by logging out, wherever in the app the stale request
 * happened to fire.
 */
let authToken: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setAuthToken(token: string | null) {
  authToken = token;
}

export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  // The token is attached here so no call site has to remember it. The auth
  // and login endpoints work with or without one.
  const headers = new Headers(init?.headers);

  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);

  try {
    response = await fetch(path, { ...init, headers });
  } catch {
    // A network-level failure usually means the API is not running, which is
    // the single most common thing to get wrong in local development.
    throw new ApiError(
      "Could not reach the API. Is the FastAPI server running?",
      0,
    );
  }

  // A 401 on a request that carried a token means the session is no longer
  // good; tell the context so it can sign the user out.
  if (response.status === 401 && authToken) {
    onUnauthorized?.();
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
  /* auth */
  login: (email: string, password: string) =>
    request<AuthResult>("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),

  register: (email: string, password: string, name: string) =>
    request<AuthResult>("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    }),

  me: () => request<AuthUser>("/auth/me"),

  /** The signed-in candidate's own applications, with where each has reached. */
  myApplications: () => request<MyApplicationsResponse>("/applications/mine"),

  /* roles & users — require roles:manage / users:manage on the server */
  listPermissions: () =>
    request<{ permissions: PermissionInfo[] }>("/auth/permissions"),

  listRoles: () => request<Role[]>("/auth/roles"),

  createRole: (role: RoleDraft) =>
    request<Role>("/auth/roles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(role),
    }),

  updateRole: (name: string, changes: Partial<RoleDraft>) =>
    request<Role>(`/auth/roles/${encodeURIComponent(name)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }),

  deleteRole: (name: string) =>
    request<{ deleted: string }>(`/auth/roles/${encodeURIComponent(name)}`, {
      method: "DELETE",
    }),

  listUsers: () => request<AuthUser[]>("/auth/users"),

  createAdminUser: (user: CreateUserDraft) =>
    request<AuthUser>("/auth/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(user),
    }),

  updateUser: (userId: string, changes: UpdateUserDraft) =>
    request<AuthUser>(`/auth/users/${userId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }),

  /* jobs */

  /**
   * Roles.
   *
   * `openOnly` is what the candidate portal passes: a draft, a role not yet
   * published, or one past its deadline must not be listed to applicants. A
   * recruiter wants all of them.
   */
  listJobs: (options: { openOnly?: boolean; status?: string } = {}) =>
    request<Job[]>(
      `/jobs/${query({
        open_only: options.openOnly ? "true" : undefined,
        status: options.status,
      })}`,
    ),

  getJob: (jobId: string) => request<Job>(`/jobs/${jobId}`),

  /** Partial update. An explicit null clears a date. */
  updateJob: (jobId: string, changes: JobUpdate) =>
    request<Job>(`/jobs/${jobId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }),

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

  /**
   * Open the final, post-interview decision review.
   *
   * Runs the decision graph to its human pause and returns the model's
   * suggestion plus a `thread_id` that resumes this exact paused run when the
   * reviewer makes the call (Module 17's human-in-the-loop interrupt).
   */
  reviewDecision: (candidateId: string) =>
    request<DecisionReviewResponse>(
      `/hiring/candidates/${candidateId}/decision/review`,
      { method: "POST" },
    ),

  /** Make the final call: resume the paused graph, record it, email the candidate. */
  submitDecision: (candidateId: string, body: DecisionRequest) =>
    request<DecisionResult>(`/hiring/candidates/${candidateId}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

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

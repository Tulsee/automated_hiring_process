/**
 * Shared test helpers.
 *
 * The API module is mocked per test file rather than `fetch`, so a test states
 * what the backend returns in the same shape the app consumes.
 */

import type { ReactNode } from "react";
import { vi } from "vitest";
import { api, setAuthToken } from "../api/client";
import { AuthContext, type AuthState } from "../auth/context";
import type { AuthUser } from "../types";
import * as fixtures from "./fixtures";

export type ApiMock = {
  [K in keyof typeof api]: ReturnType<typeof vi.fn>;
};

/**
 * Point every API method at a resolved fixture.
 *
 * `overrides` replaces individual methods, so a test can make one call fail
 * or hang without restating the rest.
 */
export function mockApi(
  overrides: Partial<Record<keyof typeof api, unknown>> = {},
) {
  const defaults: Record<string, unknown> = {
    listJobs: async () => [fixtures.job, fixtures.designJob],
    me: async () => superadminUser,
    login: async () => ({
      access_token: "test-token",
      token_type: "bearer",
      user: superadminUser,
    }),
    register: async () => ({
      access_token: "test-token",
      token_type: "bearer",
      user: candidateUser,
    }),
    listRoles: async () => [],
    listUsers: async () => [superadminUser],
    listPermissions: async () => ({ permissions: [] }),
    createRole: async () => ({
      id: "r1", name: "x", description: "", permissions: [],
      created_by: null, created_at: null, updated_at: null,
    }),
    updateRole: async () => ({
      id: "r1", name: "x", description: "", permissions: [],
      created_by: null, created_at: null, updated_at: null,
    }),
    deleteRole: async () => ({ deleted: "x" }),
    createAdminUser: async () => superadminUser,
    updateUser: async () => superadminUser,
    createJob: async () => fixtures.job,
    // Resolve by id, so a test that edits one role does not get another.
    getJob: async (jobId: string) =>
      [
        fixtures.job,
        fixtures.designJob,
        fixtures.expiredJob,
        fixtures.draftJob,
      ].find((candidate) => candidate.id === jobId) ?? fixtures.job,
    updateJob: async () => fixtures.job,
    listCandidates: async () => fixtures.candidateList,
    getCandidate: async () => fixtures.candidateDetail,
    screenCandidate: async () => ({
      candidate_id: "cand-1",
      decision: "invited_to_interview",
      screening_score: 82.5,
      rationale: "Strong API background.",
      message: "Candidate scored 82.5/100 and passed the screening threshold.",
    }),
    health: async () => ({ status: "ok" }),
    applyToJob: async () => ({ id: "cand-9", status: "received" }),
    myApplications: async () => ({ total: 0, applications: [] }),
    reviewDecision: async () => ({
      thread_id: "decision:cand-1:abcd1234",
      review: {
        candidate_id: "cand-1",
        candidate_name: "Casey Candidate",
        job_title: "Backend Engineer",
        overall_percent: 82,
        needs_human_review: false,
        suggested_decision: "hired",
        suggested_reason: "Strong interview (82/100).",
      },
    }),
    submitDecision: async () => ({
      candidate_id: "cand-1",
      action: "approve",
      final_decision: "hired",
      message: "Advanced to an offer after interview review.",
    }),
    listSessions: async () => fixtures.sessionList,
    createSession: async () => ({
      ...fixtures.scorecard,
      id: "sess-9",
      invite_token: "tok",
      invite_url: "http://x/interview?token=tok",
    }),
    getInvite: async () => ({
      id: "sess-1",
      candidate_id: "cand-1",
      job_id: "job-1",
      current_question_index: 0,
      total_questions: 1,
      total_time_seconds: 60,
      status: "invited",
      questions: [],
      question: null,
      intro_acknowledged: false,
      invite_expires_at: null,
    }),
    acknowledgeIntro: async () => ({
      session_id: "sess-1",
      status: "in_progress",
      intro_acknowledged: true,
      total_questions: 2,
      total_time_seconds: 150,
      question: {
        id: "q_tech",
        text: "Tell us about your backend experience.",
        competency: "technical_depth",
        time_limit_seconds: 60,
      },
    }),
    uploadAnswer: async () => ({
      id: "answer-1",
      session_id: "sess-1",
      question_id: "q_tech",
      filename: "sess-1_q_tech.webm",
      status: "uploaded",
      answered_count: 1,
      total_questions: 2,
      session_status: "in_progress",
      next_question: null,
    }),
    getTranscripts: async () => fixtures.transcripts,
    transcribe: async () => ({
      session_id: "sess-1",
      transcription_status: "completed",
      total_answers: 3,
      transcribed: 3,
      skipped: 0,
      failed: 0,
      results: [],
    }),
    getScorecard: async () => fixtures.scorecard,
    score: async () => fixtures.scorecard,
    answerVideoUrl: (sessionId: string, questionId: string) =>
      `/interviews/${sessionId}/questions/${questionId}/answers`,
  };

  const spies: Record<string, ReturnType<typeof vi.fn>> = {};

  for (const [name, implementation] of Object.entries({
    ...defaults,
    ...overrides,
  })) {
    const spy = vi.fn(implementation as (...args: unknown[]) => unknown);

    vi.spyOn(api, name as keyof typeof api).mockImplementation(
      spy as never,
    );

    spies[name] = spy;
  }

  return spies as ApiMock;
}

/** A promise that never settles, for asserting loading states. */
export function pending<T>(): Promise<T> {
  return new Promise<T>(() => {});
}

/** A rejected call, for asserting error states. */
export function failing(message: string) {
  return async () => {
    throw new Error(message);
  };
}


/* ------------------------------------------------------------- auth */

export const superadminUser: AuthUser = {
  id: "user-super",
  email: "superadmin@example.com",
  name: "Super Admin",
  kind: "administration",
  role: null,
  is_superadmin: true,
  active: true,
  permissions: [
    "jobs:read",
    "jobs:write",
    "candidates:read",
    "candidates:screen",
    "interviews:read",
    "interviews:manage",
    "interviews:score",
    "roles:manage",
    "users:manage",
  ],
  created_at: null,
};

export const candidateUser: AuthUser = {
  id: "user-cand",
  email: "cand@example.com",
  name: "Candidate",
  kind: "candidate",
  role: null,
  is_superadmin: false,
  active: true,
  permissions: [],
  created_at: null,
};

/** An auth context value for a given user, with the real helpers computed. */
export function authValue(user: AuthUser | null): AuthState {
  return {
    user,
    loading: false,
    signIn: async () => {},
    register: async () => {},
    signOut: () => {},
    refresh: async () => {},
    can: (permission) =>
      Boolean(user) &&
      (user!.is_superadmin || user!.permissions.includes(permission)),
    isAdministration:
      user?.kind === "administration" || Boolean(user?.is_superadmin),
    isSuperadmin: Boolean(user?.is_superadmin),
  };
}

/**
 * Wraps a component that reads `useAuth` (e.g. AppShell) in a static context,
 * for tests that render it directly without the real provider.
 */
export function AuthHarness({
  user = superadminUser,
  children,
}: {
  user?: AuthUser | null;
  children: ReactNode;
}) {
  return (
    <AuthContext.Provider value={authValue(user)}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Make the real AuthProvider (inside <App/>) resolve to a signed-in user:
 * seed the token it looks for and point the mocked `api.me` at that user.
 * Call before rendering <App/>.
 */
export function signedIn(user: AuthUser = superadminUser) {
  localStorage.setItem("hirewise.token", "test-token");
  setAuthToken("test-token");
  return user;
}

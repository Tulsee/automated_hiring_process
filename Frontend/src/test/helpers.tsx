/**
 * Shared test helpers.
 *
 * The API module is mocked per test file rather than `fetch`, so a test states
 * what the backend returns in the same shape the app consumes.
 */

import { vi } from "vitest";
import { api } from "../api/client";
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
    createJob: async () => fixtures.job,
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
    listSessions: async () => fixtures.sessionList,
    createSession: async () => ({
      ...fixtures.scorecard,
      id: "sess-9",
      invite_token: "tok",
      invite_url: "http://x/interview?token=tok",
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

/**
 * The candidate's recording flow.
 *
 * jsdom has neither `getUserMedia` nor `MediaRecorder`, so both are stubbed
 * here. The stubs are deliberately faithful about the one thing that matters:
 * a recorder only produces its blob after `stop()` fires `onstop`, which is
 * what the flow awaits before uploading.
 *
 * The countdowns are driven with fake timers, so the 30-second preparation
 * window is asserted exactly rather than waited out.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { InterviewPage, PREPARATION_SECONDS } from "./InterviewPage";
import { PREPARATION_SECONDS as EXPORTED } from "./InterviewPage";
import { api } from "../api/client";
import { mockApi } from "../test/helpers";
import type { InterviewSession } from "../types";

const QUESTIONS = [
  {
    id: "q_tech",
    text: "Tell us about your backend experience.",
    competency: "technical_depth",
    time_limit_seconds: 60,
  },
  {
    id: "q_design",
    text: "How would you design a scalable API?",
    competency: "system_design",
    time_limit_seconds: 90,
  },
];

function session(overrides: Partial<InterviewSession> = {}): InterviewSession {
  return {
    id: "sess-1",
    candidate_id: "cand-1",
    job_id: "job-1",
    current_question_index: 0,
    total_questions: QUESTIONS.length,
    total_time_seconds: 150,
    status: "invited",
    questions: QUESTIONS,
    question: QUESTIONS[0]!,
    intro_acknowledged: false,
    invite_expires_at: "2026-12-01T00:00:00",
    ...overrides,
  };
}

/* ------------------------------------------------------- media stubs */

let tracksStopped = 0;
let recorderInstances: FakeRecorder[] = [];

class FakeRecorder {
  state: "inactive" | "recording" = "inactive";
  mimeType: string;
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;

  static isTypeSupported = (type: string) => type.startsWith("video/webm");

  constructor(_stream: MediaStream, options?: { mimeType?: string }) {
    this.mimeType = options?.mimeType ?? "video/webm";
    recorderInstances.push(this);
  }

  start() {
    this.state = "recording";
  }

  stop() {
    this.state = "inactive";
    // A real recorder flushes data before onstop; mirror that order.
    this.ondataavailable?.({ data: new Blob(["video-bytes"]) });
    this.onstop?.();
  }
}

function stubMedia({ deny = false } = {}) {
  tracksStopped = 0;
  recorderInstances = [];

  const stream = {
    getTracks: () => [
      {
        stop: () => {
          tracksStopped += 1;
        },
      },
    ],
  } as unknown as MediaStream;

  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: {
      getUserMedia: vi.fn(async () => {
        if (deny) throw new Error("Permission denied");
        return stream;
      }),
    },
  });

  vi.stubGlobal("MediaRecorder", FakeRecorder);
}

/** Walk from the invite screen to the first preparation countdown. */
async function startInterview(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: /i understand/i }));

  await user.click(
    await screen.findByRole("button", { name: /turn on camera/i }),
  );

  await screen.findByText(/to prepare/i);
}

beforeEach(() => {
  stubMedia();
  mockApi({ getInvite: async () => session() });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("getting into the interview", () => {
  it("explains the rules before anything records", async () => {
    render(<InterviewPage token="tok" />);

    expect(
      await screen.findByText(/30 seconds to prepare/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/recording starts automatically/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/one take per question/i)).toBeInTheDocument();
  });

  it("lists the questions' competencies and limits up front", async () => {
    render(<InterviewPage token="tok" />);

    expect(await screen.findByText(/technical depth · 1:00/i)).toBeInTheDocument();
    expect(screen.getByText(/system design · 1:30/i)).toBeInTheDocument();
  });

  it("acknowledges the intro against the invite token", async () => {
    const mocked = mockApi({ getInvite: async () => session() });
    const user = userEvent.setup();

    render(<InterviewPage token="tok" />);

    await user.click(
      await screen.findByRole("button", { name: /i understand/i }),
    );

    await waitFor(() =>
      expect(mocked.acknowledgeIntro).toHaveBeenCalledWith("tok"),
    );
  });

  it("asks for the camera only after the intro is accepted", async () => {
    const user = userEvent.setup();

    render(<InterviewPage token="tok" />);

    expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled();

    await user.click(
      await screen.findByRole("button", { name: /i understand/i }),
    );
    await user.click(
      await screen.findByRole("button", { name: /turn on camera/i }),
    );

    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith({
      video: true,
      audio: true,
    });
  });

  it("explains a blocked camera and offers another go", async () => {
    stubMedia({ deny: true });
    const user = userEvent.setup();

    render(<InterviewPage token="tok" />);

    await user.click(
      await screen.findByRole("button", { name: /i understand/i }),
    );
    await user.click(
      await screen.findByRole("button", { name: /turn on camera/i }),
    );

    expect(await screen.findByText(/no camera access/i)).toBeInTheDocument();
    expect(screen.getByText(/permission denied/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /try again/i }),
    ).toBeInTheDocument();
  });

  it("resumes an interview that was already started", async () => {
    mockApi({
      getInvite: async () =>
        session({ intro_acknowledged: true, status: "in_progress" }),
    });

    render(<InterviewPage token="tok" />);

    // Straight to the camera step; the intro is not shown again.
    expect(
      await screen.findByRole("button", { name: /turn on camera/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/one take per question/i)).not.toBeInTheDocument();
  });

  it("says so when the interview is already submitted", async () => {
    mockApi({ getInvite: async () => session({ status: "submitted" }) });

    render(<InterviewPage token="tok" />);

    expect(
      await screen.findByText(/interview submitted/i),
    ).toBeInTheDocument();
  });

  it("explains an expired link", async () => {
    mockApi({
      getInvite: async () => {
        throw new Error("This interview invite link has expired");
      },
    });

    render(<InterviewPage token="tok" />);

    expect(
      await screen.findByText(/this link does not work/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/invite links expire/i)).toBeInTheDocument();
  });
});

describe("the 30-second preparation window", () => {
  it("shows the question with nothing recording yet", async () => {
    const user = userEvent.setup();

    render(<InterviewPage token="tok" />);
    await startInterview(user);

    expect(
      screen.getByText("Tell us about your backend experience."),
    ).toBeInTheDocument();
    // The clock is the authoritative readout; the prose repeats it.
    expect(screen.getByRole("status")).toHaveTextContent("0:30");
    // No recorder has been constructed, so nothing is being captured.
    expect(recorderInstances).toHaveLength(0);
    expect(screen.queryByText("Recording")).not.toBeInTheDocument();
  });

  it("is exactly the documented duration", () => {
    expect(PREPARATION_SECONDS).toBe(30);
    expect(EXPORTED).toBe(30);
  });

  it("counts down", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    render(<InterviewPage token="tok" />);
    await startInterview(user);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });

    expect(screen.getByRole("status")).toHaveTextContent("0:20");
  });

  it("starts recording automatically when it runs out", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    render(<InterviewPage token="tok" />);
    await startInterview(user);

    expect(recorderInstances).toHaveLength(0);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(PREPARATION_SECONDS * 1000 + 500);
    });

    // The candidate pressed nothing; recording began on its own.
    expect(recorderInstances).toHaveLength(1);
    expect(recorderInstances[0]!.state).toBe("recording");
    expect(await screen.findByText("Recording")).toBeInTheDocument();
  });

  it("lets a ready candidate start early", async () => {
    const user = userEvent.setup();

    render(<InterviewPage token="tok" />);
    await startInterview(user);

    await user.click(screen.getByRole("button", { name: /i am ready/i }));

    expect(recorderInstances).toHaveLength(1);
    expect(screen.getByText("Recording")).toBeInTheDocument();
  });

  it("runs again before the next question", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    mockApi({
      getInvite: async () => session(),
      uploadAnswer: async () => ({
        id: "a1",
        session_id: "sess-1",
        question_id: "q_tech",
        filename: "f.webm",
        status: "uploaded",
        answered_count: 1,
        total_questions: 2,
        session_status: "in_progress",
        next_question: QUESTIONS[1]!,
      }),
    });

    render(<InterviewPage token="tok" />);
    await startInterview(user);

    await user.click(screen.getByRole("button", { name: /i am ready/i }));
    await user.click(screen.getByRole("button", { name: /finish this answer/i }));

    // The second question gets its own preparation window.
    expect(
      await screen.findByText("How would you design a scalable API?"),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("0:30");
    expect(screen.getByRole("status")).toHaveTextContent(/to prepare/i);
  });
});

describe("recording an answer", () => {
  it("shows the question's own limit, not the preparation time", async () => {
    const user = userEvent.setup();

    render(<InterviewPage token="tok" />);
    await startInterview(user);

    await user.click(screen.getByRole("button", { name: /i am ready/i }));

    expect(screen.getByText(/1:00/)).toBeInTheDocument();
    expect(screen.getByText(/left to answer/i)).toBeInTheDocument();
  });

  it("stops and uploads automatically at the limit", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    const mocked = mockApi({ getInvite: async () => session() });

    render(<InterviewPage token="tok" />);
    await startInterview(user);

    await user.click(screen.getByRole("button", { name: /i am ready/i }));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000 + 500);
    });

    await waitFor(() => expect(mocked.uploadAnswer).toHaveBeenCalled());

    const [sessionId, questionId, blob] = mocked.uploadAnswer.mock.calls[0]!;

    expect(sessionId).toBe("sess-1");
    expect(questionId).toBe("q_tech");
    expect(blob).toBeInstanceOf(Blob);
    expect((blob as Blob).size).toBeGreaterThan(0);
  });

  it("uploads when the candidate finishes early", async () => {
    const mocked = mockApi({ getInvite: async () => session() });
    const user = userEvent.setup();

    render(<InterviewPage token="tok" />);
    await startInterview(user);

    await user.click(screen.getByRole("button", { name: /i am ready/i }));
    await user.click(screen.getByRole("button", { name: /finish this answer/i }));

    await waitFor(() =>
      expect(mocked.uploadAnswer).toHaveBeenCalledWith(
        "sess-1",
        "q_tech",
        expect.any(Blob),
      ),
    );
  });

  it("uses a fresh recorder per question, since one cannot restart", async () => {
    mockApi({
      getInvite: async () => session(),
      uploadAnswer: async () => ({
        id: "a1",
        session_id: "sess-1",
        question_id: "q_tech",
        filename: "f.webm",
        status: "uploaded",
        answered_count: 1,
        total_questions: 2,
        session_status: "in_progress",
        next_question: QUESTIONS[1]!,
      }),
    });

    const user = userEvent.setup();

    render(<InterviewPage token="tok" />);
    await startInterview(user);

    await user.click(screen.getByRole("button", { name: /i am ready/i }));
    await user.click(screen.getByRole("button", { name: /finish this answer/i }));

    await screen.findByText("How would you design a scalable API?");

    await user.click(screen.getByRole("button", { name: /i am ready/i }));

    expect(recorderInstances).toHaveLength(2);
  });

  it("finishes the interview when the last answer is in", async () => {
    mockApi({
      getInvite: async () => session(),
      uploadAnswer: async () => ({
        id: "a2",
        session_id: "sess-1",
        question_id: "q_design",
        filename: "f.webm",
        status: "uploaded",
        answered_count: 2,
        total_questions: 2,
        session_status: "submitted",
        next_question: null,
      }),
    });

    const user = userEvent.setup();

    render(<InterviewPage token="tok" />);
    await startInterview(user);

    await user.click(screen.getByRole("button", { name: /i am ready/i }));
    await user.click(screen.getByRole("button", { name: /finish this answer/i }));

    expect(
      await screen.findByText(/interview submitted/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/a recruiter reviews every interview/i)).toBeInTheDocument();
  });

  it("releases the camera once the interview ends", async () => {
    mockApi({
      getInvite: async () => session(),
      uploadAnswer: async () => ({
        id: "a2",
        session_id: "sess-1",
        question_id: "q_tech",
        filename: "f.webm",
        status: "uploaded",
        answered_count: 2,
        total_questions: 2,
        session_status: "submitted",
        next_question: null,
      }),
    });

    const user = userEvent.setup();

    render(<InterviewPage token="tok" />);
    await startInterview(user);

    await user.click(screen.getByRole("button", { name: /i am ready/i }));
    await user.click(screen.getByRole("button", { name: /finish this answer/i }));

    await screen.findByText(/interview submitted/i);

    // A camera light left on after the interview is a bug a candidate sees.
    expect(tracksStopped).toBeGreaterThan(0);
  });

  it("reports an upload failure instead of losing it silently", async () => {
    mockApi({
      getInvite: async () => session(),
      uploadAnswer: async () => {
        throw new Error("This question has already been answered");
      },
    });

    const user = userEvent.setup();

    render(<InterviewPage token="tok" />);
    await startInterview(user);

    await user.click(screen.getByRole("button", { name: /i am ready/i }));
    await user.click(screen.getByRole("button", { name: /finish this answer/i }));

    expect(
      await screen.findByText(/already been answered/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/your answer was not saved/i)).toBeInTheDocument();
  });

  it("announces the clock politely rather than interrupting", async () => {
    const user = userEvent.setup();

    render(<InterviewPage token="tok" />);
    await startInterview(user);

    const clock = screen.getByRole("status");

    expect(clock).toHaveAttribute("aria-live", "polite");
    expect(clock).toHaveTextContent(/to prepare/i);
  });
});

describe("routing", () => {
  it("never calls a recruiter endpoint from the candidate flow", async () => {
    const mocked = mockApi({ getInvite: async () => session() });
    const user = userEvent.setup();

    render(<InterviewPage token="tok" />);
    await startInterview(user);

    expect(mocked.listCandidates).not.toHaveBeenCalled();
    expect(mocked.listSessions).not.toHaveBeenCalled();
    expect(api.getInvite).toHaveBeenCalledWith("tok");
  });
});

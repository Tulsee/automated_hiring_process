/**
 * The inline action offered per candidate row.
 *
 * The behaviour worth pinning down is that the column shows the *one* step
 * that candidate is actually waiting on, so a recruiter can move a whole list
 * forward without opening anyone.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CandidateRowActions } from "./CandidateRowActions";
import { failing, mockApi } from "../test/helpers";
import * as fixtures from "../test/fixtures";
import type { CandidateSummary } from "../types";

function row(overrides: Partial<CandidateSummary> = {}): CandidateSummary {
  return {
    ...fixtures.candidateList.candidates[0]!,
    ...overrides,
  };
}

function renderActions(
  candidate: CandidateSummary,
  onChanged = vi.fn(),
) {
  render(<CandidateRowActions candidate={candidate} onChanged={onChanged} />);

  return onChanged;
}

/**
 * `userEvent.setup()` installs its own clipboard stub, so the assertions read
 * back what landed on the clipboard rather than spying on `writeText` — a spy
 * installed before `setup()` is simply replaced, and would record nothing.
 */
function breakClipboard() {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: {
      writeText: async () => {
        throw new Error("not allowed");
      },
    },
  });
}

beforeEach(() => {
  mockApi();
});

describe("which action a row offers", () => {
  it("offers screening when there is no decision yet", () => {
    renderActions(row({ decision: null, interview_session_id: null }));

    expect(
      screen.getByRole("button", { name: /run screening decision for/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /interview invite/i }),
    ).not.toBeInTheDocument();
  });

  it("offers an invite once decided and eligible", () => {
    renderActions(
      row({ decision: "invited_to_interview", interview_session_id: null }),
    );

    expect(
      screen.getByRole("button", { name: /create an interview invite for/i }),
    ).toBeInTheDocument();
  });

  it("accepts the older decision spelling too", () => {
    renderActions(
      row({ decision: "invite_to_interview", interview_session_id: null }),
    );

    expect(
      screen.getByRole("button", { name: /create an interview invite for/i }),
    ).toBeInTheDocument();
  });

  it("offers the link once a session exists", () => {
    renderActions(
      row({ decision: "invited_to_interview", interview_session_id: "sess-1" }),
    );

    expect(
      screen.getByRole("button", { name: /copy the interview invite link/i }),
    ).toBeInTheDocument();
  });

  it("offers nothing for a candidate who was not progressed", () => {
    renderActions(row({ decision: "reject", interview_session_id: null }));

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByText("--")).toBeInTheDocument();
  });

  it("names the candidate, so rows are distinguishable to a screen reader", () => {
    renderActions(row({ name: "Bo Lin", decision: null }));

    expect(
      screen.getByRole("button", {
        name: "Run screening decision for Bo Lin",
      }),
    ).toBeInTheDocument();
  });

  it("copes with an unnamed candidate", () => {
    renderActions(row({ name: null, decision: null }));

    expect(
      screen.getByRole("button", {
        name: /run screening decision for this candidate/i,
      }),
    ).toBeInTheDocument();
  });
});

describe("running the screening decision", () => {
  it("calls the hiring endpoint and refreshes the list", async () => {
    const api = mockApi();
    const user = userEvent.setup();
    const onChanged = renderActions(row({ decision: null }));

    await user.click(
      screen.getByRole("button", { name: /run screening decision for/i }),
    );

    await waitFor(() =>
      expect(api.screenCandidate).toHaveBeenCalledWith("cand-1"),
    );
    expect(onChanged).toHaveBeenCalled();
  });

  it("reports the decision it reached", async () => {
    mockApi();
    const user = userEvent.setup();
    renderActions(row({ decision: null }));

    await user.click(
      screen.getByRole("button", { name: /run screening decision for/i }),
    );

    expect(
      await screen.findByText(/decision: invited to interview/i),
    ).toBeInTheDocument();
  });

  it("surfaces a failure on the row rather than silently failing", async () => {
    mockApi({ screenCandidate: failing("Job with ID x not found.") });
    const user = userEvent.setup();
    const onChanged = renderActions(row({ decision: null }));

    await user.click(
      screen.getByRole("button", { name: /run screening decision for/i }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(/not found/i);
    // Nothing changed, so the list must not be reloaded.
    expect(onChanged).not.toHaveBeenCalled();
  });

  it("disables the button while it runs, since it is slow", async () => {
    let release = () => {};

    mockApi({
      screenCandidate: () =>
        new Promise((resolve) => {
          release = () =>
            resolve({
              candidate_id: "cand-1",
              decision: "invited_to_interview",
              screening_score: 80,
              rationale: null,
              message: null,
            });
        }),
    });

    const user = userEvent.setup();
    renderActions(row({ decision: null }));

    const button = screen.getByRole("button", {
      name: /run screening decision for/i,
    });

    await user.click(button);

    expect(button).toBeDisabled();
    expect(button).toHaveTextContent(/screening…/i);

    release();

    await waitFor(() => expect(button).not.toBeDisabled());
  });
});

describe("creating an invite", () => {
  it("creates the session and copies the link", async () => {
    const api = mockApi();
    const user = userEvent.setup();
    const onChanged = renderActions(
      row({ decision: "invited_to_interview", interview_session_id: null }),
    );

    await user.click(
      screen.getByRole("button", { name: /create an interview invite for/i }),
    );

    await waitFor(() => expect(api.createSession).toHaveBeenCalledWith("cand-1"));

    await expect(navigator.clipboard.readText()).resolves.toBe(
      "http://x/interview?token=tok",
    );
    expect(await screen.findByText(/invite link copied/i)).toBeInTheDocument();
    expect(onChanged).toHaveBeenCalled();
  });

  it("shows the link when the clipboard is unavailable", async () => {
    mockApi();
    const user = userEvent.setup();

    // Clipboard access needs a secure context, which plain HTTP is not. The
    // override goes after setup(), which installs a working stub of its own.
    breakClipboard();
    renderActions(
      row({ decision: "invited_to_interview", interview_session_id: null }),
    );

    await user.click(
      screen.getByRole("button", { name: /create an interview invite for/i }),
    );

    expect(
      await screen.findByText("http://x/interview?token=tok"),
    ).toBeInTheDocument();
  });

  it("reports an ineligible candidate", async () => {
    mockApi({
      createSession: failing("Candidate is not eligible for an interview session"),
    });
    const user = userEvent.setup();
    renderActions(
      row({ decision: "invited_to_interview", interview_session_id: null }),
    );

    await user.click(
      screen.getByRole("button", { name: /create an interview invite for/i }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(/not eligible/i);
  });
});

describe("copying an existing invite", () => {
  it("reads the candidate to get the link, then copies it", async () => {
    const api = mockApi();
    const user = userEvent.setup();

    renderActions(
      row({ decision: "invited_to_interview", interview_session_id: "sess-1" }),
    );

    await user.click(
      screen.getByRole("button", { name: /copy the interview invite link/i }),
    );

    // The list row carries the session id but not the URL.
    await waitFor(() => expect(api.getCandidate).toHaveBeenCalledWith("cand-1"));

    await expect(navigator.clipboard.readText()).resolves.toBe(
      fixtures.candidateDetail.interview.invite_url,
    );
  });

  it("says so when the session has no stored link", async () => {
    mockApi({
      getCandidate: async () => ({
        ...fixtures.candidateDetail,
        interview: {
          ...fixtures.candidateDetail.interview,
          invite_url: null,
        },
      }),
    });

    const user = userEvent.setup();

    renderActions(
      row({ decision: "invited_to_interview", interview_session_id: "sess-1" }),
    );

    await user.click(
      screen.getByRole("button", { name: /copy the interview invite link/i }),
    );

    expect(
      await screen.findByText(/no invite link stored/i),
    ).toBeInTheDocument();
  });
});

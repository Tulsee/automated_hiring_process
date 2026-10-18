/**
 * The candidate's application tracker: the roles they applied to, where each
 * one has reached, and what's left.
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MyApplicationsPage } from "./MyApplicationsPage";
import { mockApi } from "../test/helpers";
import type { JourneyStep, MyApplication } from "../types";

function stepOf(over: Partial<JourneyStep> = {}): JourneyStep {
  return { key: "applied", title: "Applied", state: "done", detail: "", ...over };
}

function applicationOf(over: Partial<MyApplication> = {}): MyApplication {
  const steps: JourneyStep[] = [
    stepOf({ key: "applied", title: "Applied", state: "done" }),
    stepOf({ key: "screening", title: "Screening", state: "done" }),
    stepOf({ key: "decision", title: "Screening decision", state: "done" }),
    stepOf({
      key: "interview",
      title: "Interview",
      state: "current",
      detail: "Open your interview invite link to record your answers.",
    }),
    stepOf({ key: "assessment", title: "Assessment", state: "pending" }),
    stepOf({ key: "outcome", title: "Outcome", state: "pending" }),
  ];

  return {
    id: "cand-1",
    job_id: "job-1",
    job_title: "Backend Engineer",
    status: "processed",
    decision: "invited_to_interview",
    screening_score: 82,
    applied_at: "2026-01-05T00:00:00Z",
    current_step: steps[3]!,
    completed_steps: 3,
    total_steps: 6,
    steps,
    interview_invite_url: "http://x/interview?token=abc",
    interview_status: "invited",
    ...over,
  };
}

describe("MyApplicationsPage", () => {
  it("lists each application with its job and progress", async () => {
    mockApi({
      myApplications: async () => ({
        total: 1,
        applications: [applicationOf()],
      }),
    });

    render(<MyApplicationsPage onBrowseRoles={vi.fn()} />);

    expect(
      await screen.findByRole("heading", { name: /backend engineer/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/3 of 6 steps complete/i)).toBeInTheDocument();
  });

  it("surfaces the current step and the interview link when one is waiting", async () => {
    mockApi({
      myApplications: async () => ({
        total: 1,
        applications: [applicationOf()],
      }),
    });

    render(<MyApplicationsPage onBrowseRoles={vi.fn()} />);

    await screen.findByRole("heading", { name: /backend engineer/i });

    // The invite prompt appears both in the "now" block and in the journey
    // step; assert on the "what's happening now" block specifically.
    const now = screen.getByText(/what's happening now/i)
      .parentElement as HTMLElement;
    expect(
      within(now).getByText(/open your interview invite link/i),
    ).toBeInTheDocument();

    const link = screen.getByRole("link", { name: /record your interview/i });
    expect(link).toHaveAttribute("href", "http://x/interview?token=abc");
  });

  it("does not show the record link once the interview is submitted", async () => {
    mockApi({
      myApplications: async () => ({
        total: 1,
        applications: [
          applicationOf({
            interview_status: "submitted",
            current_step: stepOf({
              key: "assessment",
              title: "Assessment",
              state: "current",
            }),
          }),
        ],
      }),
    });

    render(<MyApplicationsPage onBrowseRoles={vi.fn()} />);

    await screen.findByRole("heading", { name: /backend engineer/i });

    expect(
      screen.queryByRole("link", { name: /record your interview/i }),
    ).not.toBeInTheDocument();
  });

  it("shows every journey step", async () => {
    mockApi({
      myApplications: async () => ({
        total: 1,
        applications: [applicationOf()],
      }),
    });

    render(<MyApplicationsPage onBrowseRoles={vi.fn()} />);

    const list = await screen.findByRole("list");
    for (const title of [
      "Applied",
      "Screening",
      "Screening decision",
      "Interview",
      "Assessment",
      "Outcome",
    ]) {
      expect(within(list).getByText(title)).toBeInTheDocument();
    }
  });

  it("invites a first-timer to browse roles", async () => {
    const onBrowseRoles = vi.fn();
    mockApi({ myApplications: async () => ({ total: 0, applications: [] }) });

    const user = userEvent.setup();
    render(<MyApplicationsPage onBrowseRoles={onBrowseRoles} />);

    await screen.findByText(/haven't applied to anything yet/i);

    await user.click(screen.getByRole("button", { name: /browse open roles/i }));

    expect(onBrowseRoles).toHaveBeenCalledOnce();
  });
});

/**
 * The diagnostics panel, and the API status indicator.
 *
 * Both exist to make previously unreachable endpoints usable:
 * `/applications/{id}/screening`, `/applications/{id}/vector` and `/health`.
 */

import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CandidateDiagnostics } from "./CandidateDiagnostics";
import { ApiStatus } from "./ApiStatus";
import { ApiError } from "../api/client";
import { failing, mockApi, pending } from "../test/helpers";

const COMPLETE = {
  candidate_id: "cand-1",
  candidate_name: "Ama Boateng",
  screening_score: 77.38,
  semantic_similarity: 66.77,
  skill_score: 80,
  experience_score: 100,
  matched_skills: ["docker", "fastapi", "mongodb", "python"],
  missing_skills: ["langchain"],
  rationale: "Candidate scored 77.4/100.",
};

const PENDING = {
  candidate_id: "cand-1",
  status: "error",
  message: "Screening has not completed yet",
};

const VECTOR = {
  candidate_id: "cand-1",
  payload: {
    candidate_id: "cand-1",
    job_id: "job-1",
    name: "Ama Boateng",
    skills: ["python", "fastapi", "mongodb"],
  },
  vector_dimensions: 768,
};

async function openPanel() {
  const user = userEvent.setup();

  render(<CandidateDiagnostics candidateId="cand-1" />);

  await user.click(screen.getByRole("button", { name: /processing detail/i }));

  return user;
}

describe("the diagnostics panel", () => {
  it("is collapsed until opened, so it costs no requests", () => {
    const api = mockApi({
      getCandidateScreening: async () => COMPLETE,
      getCandidateVector: async () => VECTOR,
    });

    render(<CandidateDiagnostics candidateId="cand-1" />);

    expect(
      screen.getByRole("button", { name: /processing detail/i }),
    ).toHaveAttribute("aria-expanded", "false");

    expect(api.getCandidateScreening).not.toHaveBeenCalled();
    expect(api.getCandidateVector).not.toHaveBeenCalled();
  });

  it("fetches both endpoints when opened", async () => {
    const api = mockApi({
      getCandidateScreening: async () => COMPLETE,
      getCandidateVector: async () => VECTOR,
    });

    await openPanel();

    await waitFor(() =>
      expect(api.getCandidateScreening).toHaveBeenCalledWith("cand-1"),
    );
    expect(api.getCandidateVector).toHaveBeenCalledWith("cand-1");
  });

  it("shows the score the screening endpoint reports", async () => {
    mockApi({
      getCandidateScreening: async () => COMPLETE,
      getCandidateVector: async () => VECTOR,
    });

    await openPanel();

    expect(await screen.findByText("77.38 / 100")).toBeInTheDocument();
    expect(
      screen.getByText(/matched 4 required skills, 1 missing/i),
    ).toBeInTheDocument();
  });

  it("distinguishes 'not screened yet' from 'screened with no score'", async () => {
    // This is the whole reason the endpoint is worth calling separately: the
    // candidate detail only carries a stored score, so it cannot say this.
    mockApi({
      getCandidateScreening: async () => PENDING,
      getCandidateVector: async () => VECTOR,
    });

    await openPanel();

    expect(
      await screen.findByText(/screening has not completed yet/i),
    ).toBeInTheDocument();
  });

  it("reports the vector dimensions and payload", async () => {
    mockApi({
      getCandidateScreening: async () => COMPLETE,
      getCandidateVector: async () => VECTOR,
    });

    await openPanel();

    expect(await screen.findByText("768 dimensions")).toBeInTheDocument();
    expect(screen.getByText("job_id")).toBeInTheDocument();
    expect(
      screen.getByText(/3 items: python, fastapi, mongodb/i),
    ).toBeInTheDocument();
  });

  it("treats a missing embedding as information, not an error", async () => {
    mockApi({
      getCandidateScreening: async () => COMPLETE,
      getCandidateVector: async () => {
        throw new ApiError("Candidate embedding not found", 404);
      },
    });

    await openPanel();

    expect(
      await screen.findByText(/no embedding stored for this candidate/i),
    ).toBeInTheDocument();
    // A 404 must not be shouted about as a failure.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("surfaces a real vector-store failure", async () => {
    mockApi({
      getCandidateScreening: async () => COMPLETE,
      getCandidateVector: async () => {
        throw new ApiError("Qdrant unavailable", 500);
      },
    });

    await openPanel();

    expect(await screen.findByText(/qdrant unavailable/i)).toBeInTheDocument();
  });

  it("surfaces a screening failure", async () => {
    mockApi({
      getCandidateScreening: failing("Invalid candidate ID"),
      getCandidateVector: async () => VECTOR,
    });

    await openPanel();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /invalid candidate id/i,
    );
  });

  it("closes again", async () => {
    mockApi({
      getCandidateScreening: async () => COMPLETE,
      getCandidateVector: async () => VECTOR,
    });

    const user = await openPanel();

    await user.click(
      screen.getByRole("button", { name: /processing detail/i }),
    );

    expect(screen.queryByText("768 dimensions")).not.toBeInTheDocument();
  });
});

describe("the API status indicator", () => {
  it("reports a reachable API", async () => {
    mockApi();

    render(<ApiStatus />);

    expect(await screen.findByText(/api ok/i)).toBeInTheDocument();
  });

  it("says so when the API cannot be reached", async () => {
    // Otherwise an empty dashboard looks the same as a dead backend.
    mockApi({ health: failing("Could not reach the API") });

    render(<ApiStatus />);

    expect(await screen.findByText(/api unreachable/i)).toBeInTheDocument();
  });

  it("shows a checking state first", () => {
    mockApi({ health: pending });

    render(<ApiStatus />);

    expect(screen.getByText(/checking api/i)).toBeInTheDocument();
  });
});

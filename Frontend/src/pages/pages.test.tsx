/**
 * Every UI container, rendered against mocked API responses.
 *
 * These are the tests that catch "the page does not render": each asserts the
 * container reaches its loaded state and shows the data it was given, plus how
 * it behaves while loading, when empty, and when the API fails.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DashboardPage } from "./DashboardPage";
import { JobsPage } from "./JobsPage";
import { CandidatesPage } from "./CandidatesPage";
import { ReviewPage } from "./ReviewPage";
import { InterviewsPage } from "./InterviewsPage";
import { CandidatePortalPage } from "./CandidatePortalPage";
import { failing, mockApi, pending } from "../test/helpers";
import * as fixtures from "../test/fixtures";
import { formatDate } from "../lib/format";

describe("DashboardPage", () => {
  beforeEach(() => mockApi());

  it("renders the metrics once loaded", async () => {
    render(
      <DashboardPage
        onNavigate={() => {}}
        onOpenCandidate={() => {}}
        onCreateJob={() => {}}
      />,
    );

    expect(await screen.findByText("Candidates")).toBeInTheDocument();
    expect(screen.getByText(/average screening score/i)).toBeInTheDocument();
    expect(screen.getByText(/flagged for review/i)).toBeInTheDocument();
  });

  it("counts the pipeline from the real lists", async () => {
    render(
      <DashboardPage
        onNavigate={() => {}}
        onOpenCandidate={() => {}}
        onCreateJob={() => {}}
      />,
    );

    // two candidates, one of them scored
    await waitFor(() =>
      expect(screen.getByText("Applied")).toBeInTheDocument(),
    );
    expect(screen.getByText("Screened")).toBeInTheDocument();
    expect(screen.getByText("Ready to review")).toBeInTheDocument();
  });

  it("averages only the scored candidates", async () => {
    render(
      <DashboardPage
        onNavigate={() => {}}
        onOpenCandidate={() => {}}
        onCreateJob={() => {}}
      />,
    );

    // one score of 82.5 among two candidates
    expect(await screen.findByText("82.5")).toBeInTheDocument();
    expect(screen.getByText("1 scored")).toBeInTheDocument();
  });

  it("lists recent candidates", async () => {
    render(
      <DashboardPage
        onNavigate={() => {}}
        onOpenCandidate={() => {}}
        onCreateJob={() => {}}
      />,
    );

    expect(await screen.findByText("Ama Boateng")).toBeInTheDocument();
    expect(screen.getByText("Bo Lin")).toBeInTheDocument();
  });

  it("opens a candidate when their row is clicked", async () => {
    const onOpenCandidate = vi.fn();
    const user = userEvent.setup();

    render(
      <DashboardPage
        onNavigate={() => {}}
        onOpenCandidate={onOpenCandidate}
        onCreateJob={() => {}}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /ama boateng/i }));

    expect(onOpenCandidate).toHaveBeenCalledWith("cand-1");
  });

  it("navigates to the review queue", async () => {
    const onNavigate = vi.fn();
    const user = userEvent.setup();

    render(
      <DashboardPage
        onNavigate={onNavigate}
        onOpenCandidate={() => {}}
        onCreateJob={() => {}}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: /open review queue/i }),
    );

    expect(onNavigate).toHaveBeenCalledWith("review");
  });

  it("surfaces an API failure instead of rendering blank", async () => {
    mockApi({ listCandidates: failing("Could not reach the API") });

    render(
      <DashboardPage
        onNavigate={() => {}}
        onOpenCandidate={() => {}}
        onCreateJob={() => {}}
      />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /could not reach the api/i,
    );
  });
});

describe("JobsPage", () => {
  beforeEach(() => mockApi());

  function renderJobs(props: Partial<Parameters<typeof JobsPage>[0]> = {}) {
    return render(
      <JobsPage
        search=""
        createOpen={false}
        onCreateOpenChange={() => {}}
        onViewCandidates={() => {}}
        {...props}
      />,
    );
  }

  it("renders a card per role", async () => {
    renderJobs();

    expect(await screen.findByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Product Designer")).toBeInTheDocument();
  });

  it("shows how many candidates each role has drawn", async () => {
    renderJobs();

    const card = (await screen.findByText("Backend Engineer")).closest(
      ".job-card",
    )!;

    // Both fixture candidates belong to this role. Scoped to the stats
    // block, since the action button is also labelled "Candidates".
    const stats = (card as HTMLElement).querySelector(".job-stats")!;

    expect(within(stats as HTMLElement).getByText("2")).toBeInTheDocument();
    expect(
      within(stats as HTMLElement).getByText("Candidates"),
    ).toBeInTheDocument();
  });

  it("shows a loading state first", () => {
    mockApi({ listJobs: pending });

    renderJobs();

    expect(screen.getByRole("status")).toHaveTextContent(/loading roles/i);
  });

  it("says so when there are no roles", async () => {
    mockApi({ listJobs: async () => [] });

    renderJobs();

    expect(await screen.findByText(/no roles yet/i)).toBeInTheDocument();
  });

  it("filters by the global search term", async () => {
    renderJobs({ search: "designer" });

    expect(await screen.findByText("Product Designer")).toBeInTheDocument();
    expect(screen.queryByText("Backend Engineer")).not.toBeInTheDocument();
  });

  it("asks for the candidates of a role", async () => {
    const onViewCandidates = vi.fn();
    const user = userEvent.setup();

    renderJobs({ onViewCandidates });

    const cards = await screen.findAllByRole("button", {
      name: /view candidates for/i,
    });

    await user.click(cards[0]!);

    expect(onViewCandidates).toHaveBeenCalledWith("job-1");
  });

  it("creates a role from the dialog", async () => {
    const api = mockApi();
    const user = userEvent.setup();

    renderJobs({ createOpen: true });

    const dialog = screen.getByRole("dialog", { name: /create a role/i });

    await user.type(within(dialog).getByLabelText(/role title/i), "SRE");
    await user.type(
      within(dialog).getByLabelText(/description/i),
      "Keep it running",
    );
    await user.type(
      within(dialog).getByLabelText(/required skills/i),
      "linux, python",
    );

    await user.click(
      within(dialog).getByRole("button", { name: /create role/i }),
    );

    await waitFor(() => expect(api.createJob).toHaveBeenCalled());

    expect(api.createJob).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "SRE",
        required_skills: ["linux", "python"],
      }),
    );
  });

  it("will not submit an incomplete role", async () => {
    mockApi();

    renderJobs({ createOpen: true });

    expect(
      screen.getByRole("button", { name: /create role/i }),
    ).toBeDisabled();
  });
});

describe("CandidatesPage", () => {
  beforeEach(() => mockApi());

  function renderCandidates(
    props: Partial<Parameters<typeof CandidatesPage>[0]> = {},
  ) {
    return render(
      <CandidatesPage
        search=""
        jobFilter=""
        onJobFilterChange={() => {}}
        openCandidateId={null}
        onOpenCandidate={() => {}}
        {...props}
      />,
    );
  }

  it("renders the table with every candidate", async () => {
    renderCandidates();

    expect(await screen.findByText("Ama Boateng")).toBeInTheDocument();
    expect(screen.getByText("Bo Lin")).toBeInTheDocument();
  });

  it("shows the score and marks the unscored", async () => {
    renderCandidates();

    await screen.findByText("Ama Boateng");

    expect(screen.getByLabelText("82.5 out of 100")).toBeInTheDocument();
    expect(screen.getByText("AI score")).toBeInTheDocument();
    // Bo Lin has no score, so the cell is a dash explaining itself on hover.
    expect(screen.getByTitle("Not scored yet")).toBeInTheDocument();
  });

  it("asks the API for the chosen role", async () => {
    const api = mockApi();
    const onJobFilterChange = vi.fn();
    const user = userEvent.setup();

    renderCandidates({ onJobFilterChange });

    await screen.findByText("Ama Boateng");

    await user.selectOptions(
      screen.getByLabelText(/filter by role/i),
      "job-1",
    );

    expect(onJobFilterChange).toHaveBeenCalledWith("job-1");
    expect(api.listCandidates).toHaveBeenCalled();
  });

  it("re-queries when the sort changes", async () => {
    const api = mockApi();
    const user = userEvent.setup();

    renderCandidates();

    await screen.findByText("Ama Boateng");

    await user.selectOptions(screen.getByLabelText(/sort by/i), "recent");

    await waitFor(() =>
      expect(api.listCandidates).toHaveBeenCalledWith(
        expect.objectContaining({ sort: "recent" }),
      ),
    );
  });

  it("filters by name in the page", async () => {
    renderCandidates({ search: "bo lin" });

    expect(await screen.findByText("Bo Lin")).toBeInTheDocument();
    expect(screen.queryByText("Ama Boateng")).not.toBeInTheDocument();
  });

  it("disables paging at the ends", async () => {
    renderCandidates();

    await screen.findByText("Ama Boateng");

    expect(screen.getByRole("button", { name: /previous/i })).toBeDisabled();
    // two of two rows, so there is no next page
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });

  it("opens the detail dialog with the screening breakdown", async () => {
    renderCandidates({ openCandidateId: "cand-1" });

    const dialog = await screen.findByRole("dialog");

    expect(within(dialog).getByText("Ama Boateng")).toBeInTheDocument();
    expect(
      within(dialog).getByLabelText("Screening score 82.5 out of 100"),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText(/strong api background/i),
    ).toBeInTheDocument();
  });

  it("shows matched and missing skills in the detail", async () => {
    renderCandidates({ openCandidateId: "cand-1" });

    const dialog = await screen.findByRole("dialog");

    expect(
      within(dialog).getByRole("heading", { name: "Skills matched" }),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByRole("heading", {
        name: /required skills not found/i,
      }),
    ).toBeInTheDocument();
    expect(within(dialog).getByText("kubernetes")).toBeInTheDocument();
  });
});

describe("ReviewPage", () => {
  beforeEach(() => mockApi());

  it("lists submitted interviews only", async () => {
    render(<ReviewPage search="" />);

    // Named twice: once in the queue, once in the open detail panel.
    expect(await screen.findAllByText("Ama Boateng")).toHaveLength(2);
    // sess-2 is only "invited", so it is not reviewable.
    expect(screen.queryByText("Cem Yilmaz")).not.toBeInTheDocument();
  });

  it("renders the scorecard with its overall score", async () => {
    render(<ReviewPage search="" />);

    expect(
      await screen.findByLabelText("AI recommended score 2 out of 5"),
    ).toBeInTheDocument();
    expect(screen.getByText(/ai recommendation/i)).toBeInTheDocument();
  });

  it("puts the review warning before the score", async () => {
    render(<ReviewPage search="" />);

    const banner = await screen.findByRole("alert");

    expect(banner).toHaveTextContent(/needs a human look/i);

    const score = screen.getByLabelText("AI recommended score 2 out of 5");

    // The banner must come first in document order.
    expect(
      banner.compareDocumentPosition(score) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("shows each competency with its weight", async () => {
    render(<ReviewPage search="" />);

    expect(
      (await screen.findAllByText("Technical depth")).length,
    ).toBeGreaterThan(0);
    // Technical depth and System design are both weighted 35%.
    expect(screen.getAllByText(/weight 35%/i)).toHaveLength(2);
  });

  it("shows the evidence quote and says it was verified", async () => {
    render(<ReviewPage search="" />);

    expect(
      await screen.findByText(/stateless services behind a load balancer/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/quote verified against the transcript/i),
    ).toBeInTheDocument();
  });

  it("says plainly when a score has no quote", async () => {
    render(<ReviewPage search="" />);

    // Both the unquoted score and the unanswered question say this.
    expect(
      (await screen.findAllByText(/score not backed by a quote/i)).length,
    ).toBe(2);
  });

  it("explains the arithmetic on request", async () => {
    const user = userEvent.setup();

    render(<ReviewPage search="" />);

    await user.click(
      await screen.findByText(/how was this calculated/i),
    );

    expect(screen.getByText(/weighted_mean|weighted mean/i)).toBeInTheDocument();
    expect(screen.getByText(/problem-solving approach/i)).toBeInTheDocument();
  });

  it("scores an interview that has none", async () => {
    const api = mockApi({
      getScorecard: failing("not scored"),
    });
    const user = userEvent.setup();

    render(<ReviewPage search="" />);

    await user.click(
      await screen.findByRole("button", { name: /score this interview/i }),
    );

    await waitFor(() => expect(api.score).toHaveBeenCalledWith("sess-1"));
  });

  it("offers transcription when the interview is not transcribed", async () => {
    mockApi({
      getTranscripts: async () => ({
        ...fixtures.transcripts,
        transcription_status: "pending",
      }),
      getScorecard: failing("not scored"),
    });

    render(<ReviewPage search="" />);

    expect(
      await screen.findByRole("button", { name: /transcribe answers/i }),
    ).toBeInTheDocument();
  });

  it("says the queue is empty when nothing is submitted", async () => {
    mockApi({
      listSessions: async () => ({
        ...fixtures.sessionList,
        sessions: [fixtures.sessionList.sessions[1]!],
      }),
    });

    render(<ReviewPage search="" />);

    expect(
      await screen.findByText(/nothing to review yet/i),
    ).toBeInTheDocument();
  });

  it("records a decision locally and says nothing was sent", async () => {
    const user = userEvent.setup();

    render(<ReviewPage search="" />);

    await user.click(
      await screen.findByRole("button", { name: /advance candidate/i }),
    );

    expect(screen.getByText(/nothing was sent/i)).toBeInTheDocument();
  });
});

describe("InterviewsPage", () => {
  beforeEach(() => mockApi());

  it("renders every session", async () => {
    render(<InterviewsPage search="" />);

    expect(await screen.findByText("Ama Boateng")).toBeInTheDocument();
    expect(screen.getByText("Cem Yilmaz")).toBeInTheDocument();
  });

  it("shows answered progress per session", async () => {
    render(<InterviewsPage search="" />);

    expect(await screen.findByText(/3 of 3 answered/i)).toBeInTheDocument();
    expect(screen.getByText(/0 of 3 answered/i)).toBeInTheDocument();
  });

  it("summarises pipeline health", async () => {
    render(<InterviewsPage search="" />);

    await screen.findByText("Ama Boateng");

    expect(screen.getByText(/pipeline health/i)).toBeInTheDocument();
    expect(screen.getByText("Transcribed")).toBeInTheDocument();
    expect(screen.getByText("Scored")).toBeInTheDocument();
  });

  it("filters by status through the API", async () => {
    const api = mockApi();
    const user = userEvent.setup();

    render(<InterviewsPage search="" />);

    await screen.findByText("Ama Boateng");

    await user.selectOptions(
      screen.getByLabelText(/filter by status/i),
      "submitted",
    );

    await waitFor(() =>
      expect(api.listSessions).toHaveBeenCalledWith(
        expect.objectContaining({ status: "submitted" }),
      ),
    );
  });

  it("flags a session needing review", async () => {
    render(<InterviewsPage search="" />);

    expect(await screen.findByText("Flagged")).toBeInTheDocument();
  });

  it("says so when there are no sessions", async () => {
    mockApi({
      listSessions: async () => ({ ...fixtures.sessionList, sessions: [] }),
    });

    render(<InterviewsPage search="" />);

    expect(
      await screen.findByText(/no interview sessions/i),
    ).toBeInTheDocument();
  });
});

describe("CandidatePortalPage", () => {
  beforeEach(() => mockApi());

  it("renders the hero and open roles", async () => {
    render(<CandidatePortalPage search="" />);

    expect(
      screen.getByRole("heading", { name: /find your next role/i }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Backend Engineer")).toBeInTheDocument();
  });

  it("tells the applicant how they are assessed", () => {
    render(<CandidatePortalPage search="" />);

    expect(
      screen.getByText(/how your application is reviewed/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/a recruiter makes the final call/i),
    ).toBeInTheDocument();
  });

  it("searches roles", async () => {
    const user = userEvent.setup();

    render(<CandidatePortalPage search="" />);

    await screen.findByText("Backend Engineer");

    await user.type(screen.getByLabelText(/search open roles/i), "designer");

    expect(screen.queryByText("Backend Engineer")).not.toBeInTheDocument();
    expect(screen.getByText("Product Designer")).toBeInTheDocument();
  });

  it("submits an application with the resume", async () => {
    const api = mockApi();
    const user = userEvent.setup();

    render(<CandidatePortalPage search="" />);

    await user.click((await screen.findAllByRole("button", { name: /^apply/i }))[0]!);

    const dialog = screen.getByRole("dialog");

    const file = new File(["cv"], "cv.pdf", { type: "application/pdf" });

    await user.upload(within(dialog).getByLabelText(/resume/i), file);

    await user.click(
      within(dialog).getByRole("button", { name: /submit application/i }),
    );

    await waitFor(() => expect(api.applyToJob).toHaveBeenCalled());

    expect(api.applyToJob).toHaveBeenCalledWith("job-1", file);
  });

  it("will not submit without a resume", async () => {
    const user = userEvent.setup();

    render(<CandidatePortalPage search="" />);

    await user.click((await screen.findAllByRole("button", { name: /^apply/i }))[0]!);

    expect(
      screen.getByRole("button", { name: /submit application/i }),
    ).toBeDisabled();
  });

  it("confirms after a successful application", async () => {
    const user = userEvent.setup();

    render(<CandidatePortalPage search="" />);

    await user.click((await screen.findAllByRole("button", { name: /^apply/i }))[0]!);

    const dialog = screen.getByRole("dialog");

    await user.upload(
      within(dialog).getByLabelText(/resume/i),
      new File(["cv"], "cv.pdf", { type: "application/pdf" }),
    );

    await user.click(
      within(dialog).getByRole("button", { name: /submit application/i }),
    );

    expect(await screen.findByText(/thanks .* it's in/i)).toBeInTheDocument();
  });

  it("reports a failed application", async () => {
    mockApi({ applyToJob: failing("Resume must be a PDF or DOCX file") });
    const user = userEvent.setup();

    render(<CandidatePortalPage search="" />);

    await user.click((await screen.findAllByRole("button", { name: /^apply/i }))[0]!);

    const dialog = screen.getByRole("dialog");

    await user.upload(
      within(dialog).getByLabelText(/resume/i),
      new File(["x"], "cv.pdf", { type: "application/pdf" }),
    );

    await user.click(
      within(dialog).getByRole("button", { name: /submit application/i }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /must be a pdf or docx/i,
    );
  });
});

describe("the screening decision", () => {
  /**
   * Uploading a resume only scores a candidate; the decision step is what sets
   * `decision`, emails them and creates the interview session. It was missing
   * from the UI entirely, which left scored candidates unable to progress.
   */
  function undecided() {
    return {
      ...fixtures.candidateDetail,
      decision: null,
      decision_message: null,
      interview: {
        ...fixtures.candidateDetail.interview,
        session_id: null,
        status: null,
        total_questions: 0,
        answered_count: 0,
      },
    };
  }

  it("offers to run it for a scored but undecided candidate", async () => {
    mockApi({ getCandidate: async () => undecided() });

    render(
      <CandidatesPage
        search=""
        jobFilter=""
        onJobFilterChange={() => {}}
        openCandidateId="cand-1"
        onOpenCandidate={() => {}}
      />,
    );

    const dialog = await screen.findByRole("dialog");

    expect(
      within(dialog).getByRole("heading", { name: /screening decision/i }),
    ).toBeInTheDocument();
    expect(within(dialog).getByText(/not decided yet/i)).toBeInTheDocument();
  });

  it("calls the hiring endpoint and refreshes the candidate", async () => {
    const api = mockApi({ getCandidate: async () => undecided() });
    const user = userEvent.setup();

    render(
      <CandidatesPage
        search=""
        jobFilter=""
        onJobFilterChange={() => {}}
        openCandidateId="cand-1"
        onOpenCandidate={() => {}}
      />,
    );

    // Scoped to the dialog: the list now offers the same action per row.
    const dialog = await screen.findByRole("dialog");

    await user.click(
      within(dialog).getByRole("button", {
        name: /run screening decision/i,
      }),
    );

    await waitFor(() =>
      expect(api.screenCandidate).toHaveBeenCalledWith("cand-1"),
    );

    // The decision changes the candidate, so the detail is re-read.
    await waitFor(() =>
      expect(api.getCandidate.mock.calls.length).toBeGreaterThan(1),
    );
  });

  it("warns that it is slow, because it calls a model and sends mail", async () => {
    mockApi({ getCandidate: async () => undecided() });

    render(
      <CandidatesPage
        search=""
        jobFilter=""
        onJobFilterChange={() => {}}
        openCandidateId="cand-1"
        onOpenCandidate={() => {}}
      />,
    );

    expect(await screen.findByText(/takes a while/i)).toBeInTheDocument();
  });

  it("reports a failure instead of silently doing nothing", async () => {
    mockApi({
      getCandidate: async () => undecided(),
      screenCandidate: failing("Job with ID x not found."),
    });
    const user = userEvent.setup();

    render(
      <CandidatesPage
        search=""
        jobFilter=""
        onJobFilterChange={() => {}}
        openCandidateId="cand-1"
        onOpenCandidate={() => {}}
      />,
    );

    const dialog = await screen.findByRole("dialog");

    await user.click(
      within(dialog).getByRole("button", {
        name: /run screening decision/i,
      }),
    );

    expect(
      within(dialog).getByRole("alert"),
    ).toHaveTextContent(/not found/i);
  });

  it("does not offer it once a decision exists", async () => {
    mockApi();

    render(
      <CandidatesPage
        search=""
        jobFilter=""
        onJobFilterChange={() => {}}
        openCandidateId="cand-1"
        onOpenCandidate={() => {}}
      />,
    );

    const dialog = await screen.findByRole("dialog");

    expect(
      within(dialog).queryByRole("button", {
        name: /run screening decision/i,
      }),
    ).not.toBeInTheDocument();
  });

  it("shows the decision rationale once decided", async () => {
    mockApi();

    render(
      <CandidatesPage
        search=""
        jobFilter=""
        onJobFilterChange={() => {}}
        openCandidateId="cand-1"
        onOpenCandidate={() => {}}
      />,
    );

    const dialog = await screen.findByRole("dialog");

    expect(within(dialog).getByText("Passed the bar.")).toBeInTheDocument();
  });
});

describe("the interview section of the candidate detail", () => {
  /**
   * Regression: the invite button was shown whenever a candidate had no
   * session, regardless of their decision. A rejected candidate got a
   * "Create interview invite" button that the API answers with 400, under the
   * message "This candidate was invited before sessions were created
   * automatically" — which was simply untrue of them.
   */
  function withDecision(decision: string | null) {
    return {
      ...fixtures.candidateDetail,
      decision,
      interview: {
        ...fixtures.candidateDetail.interview,
        session_id: null,
        status: null,
        total_questions: 0,
        answered_count: 0,
      },
    };
  }

  async function openDetail() {
    render(
      <CandidatesPage
        search=""
        jobFilter=""
        onJobFilterChange={() => {}}
        openCandidateId="cand-1"
        onOpenCandidate={() => {}}
      />,
    );

    return screen.findByRole("dialog");
  }

  it("offers the invite to a candidate who passed screening", async () => {
    mockApi({ getCandidate: async () => withDecision("invited_to_interview") });

    const dialog = await openDetail();

    expect(
      within(dialog).getByRole("button", { name: /create interview invite/i }),
    ).toBeInTheDocument();
  });

  it("accepts the older decision spelling", async () => {
    mockApi({ getCandidate: async () => withDecision("invite_to_interview") });

    const dialog = await openDetail();

    expect(
      within(dialog).getByRole("button", { name: /create interview invite/i }),
    ).toBeInTheDocument();
  });

  it("does not offer it to a candidate who was not progressed", async () => {
    mockApi({ getCandidate: async () => withDecision("reject") });

    const dialog = await openDetail();

    expect(
      within(dialog).queryByRole("button", {
        name: /create interview invite/i,
      }),
    ).not.toBeInTheDocument();
    expect(
      within(dialog).getByText(/not progressed, so there is no interview/i),
    ).toBeInTheDocument();
  });

  it("does not claim a rejected candidate was invited", async () => {
    mockApi({ getCandidate: async () => withDecision("reject") });

    const dialog = await openDetail();

    expect(
      within(dialog).queryByText(/was invited before sessions/i),
    ).not.toBeInTheDocument();
  });

  it("points an undecided candidate at the screening step instead", async () => {
    mockApi({ getCandidate: async () => withDecision(null) });

    const dialog = await openDetail();

    expect(
      within(dialog).queryByRole("button", {
        name: /create interview invite/i,
      }),
    ).not.toBeInTheDocument();
    expect(
      within(dialog).getByText(/run the screening decision above first/i),
    ).toBeInTheDocument();
  });

  it("shows progress instead once a session exists", async () => {
    mockApi();

    const dialog = await openDetail();

    expect(
      within(dialog).queryByRole("button", {
        name: /create interview invite/i,
      }),
    ).not.toBeInTheDocument();
    expect(within(dialog).getByText(/answered 3 of 3/i)).toBeInTheDocument();
  });
});

describe("the job application window", () => {
  /**
   * A role that is a draft, not yet published, or past its deadline must not
   * appear to applicants — and the portal is what has to ask for that, since
   * `GET /jobs/` serves recruiters everything by default.
   */
  it("the portal asks the API for open roles only", async () => {
    const api = mockApi();

    render(<CandidatePortalPage search="" />);

    await waitFor(() => expect(api.listJobs).toHaveBeenCalled());

    expect(api.listJobs).toHaveBeenCalledWith({ openOnly: true });
  });

  it("the portal shows a role's closing date", async () => {
    mockApi({
      listJobs: async () => [
        { ...fixtures.job, deadline: "2026-12-01T23:59:00" },
      ],
    });

    render(<CandidatePortalPage search="" />);

    const card = (await screen.findByText("Backend Engineer")).closest(
      ".job-card",
    )!;

    // The label, the icon and the date are separate nodes.
    expect(card.textContent).toContain(
      `Closes ${formatDate("2026-12-01T23:59:00")}`,
    );
  });

  it("the recruiter list shows every role with its real state", async () => {
    mockApi({
      listJobs: async () => [
        fixtures.job,
        fixtures.expiredJob,
        fixtures.draftJob,
      ],
    });

    render(
      <JobsPage
        search=""
        createOpen={false}
        onCreateOpenChange={() => {}}
        onViewCandidates={() => {}}
      />,
    );

    expect(await screen.findByText("Closed Role")).toBeInTheDocument();
    expect(screen.getByText("Draft Role")).toBeInTheDocument();

    // The state comes from the backend rather than being guessed from the
    // candidate count, which is what the card used to do. Scoped per card,
    // since the page heading also contains the word "Open".
    const stateOf = (title: string) =>
      (screen.getByText(title).closest(".job-card") as HTMLElement).querySelector(
        ".status",
      )?.textContent;

    expect(stateOf("Backend Engineer")).toBe("Open");
    expect(stateOf("Closed Role")).toBe("Closed");
    expect(stateOf("Draft Role")).toBe("Draft");
  });

  it("explains why a role is not accepting applications", async () => {
    mockApi({ listJobs: async () => [fixtures.expiredJob] });

    render(
      <JobsPage
        search=""
        createOpen={false}
        onCreateOpenChange={() => {}}
        onViewCandidates={() => {}}
      />,
    );

    expect(
      await screen.findByText(/closed on 01 jan 2020/i),
    ).toBeInTheDocument();
  });

  it("shows an open role's closing date to the recruiter", async () => {
    mockApi({
      listJobs: async () => [
        { ...fixtures.job, deadline: "2026-12-01T23:59:00" },
      ],
    });

    render(
      <JobsPage
        search=""
        createOpen={false}
        onCreateOpenChange={() => {}}
        onViewCandidates={() => {}}
      />,
    );

    const card = (await screen.findByText("Backend Engineer")).closest(
      ".job-card",
    )!;

    expect(card.textContent).toContain(
      `Open until ${formatDate("2026-12-01T23:59:00")}`,
    );
  });
});

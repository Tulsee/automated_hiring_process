/**
 * Writing a role's interview questions.
 *
 * This was the missing half of the feature: the backend has accepted
 * `interview_questions` on a job since Module 11, but nothing in the UI ever
 * sent them, so questions could only be set by writing to MongoDB directly.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuestionEditor } from "./QuestionEditor";
import { JobsPage } from "../pages/JobsPage";
import { mockApi } from "../test/helpers";
import {
  blankQuestion,
  candidateTimeSeconds,
  defaultTemplate,
  uncoveredCompetencies,
  PREPARATION_SECONDS,
} from "../lib/interview";

describe("the template model", () => {
  it("offers the backend's own default set", () => {
    const template = defaultTemplate();

    expect(template).toHaveLength(3);
    expect(template.map((q) => q.competency)).toEqual([
      "technical_depth",
      "system_design",
      "problem_solving",
    ]);
    expect(template.map((q) => q.time_limit_seconds)).toEqual([60, 90, 120]);
  });

  it("gives every draft a distinct key", () => {
    const keys = [...defaultTemplate(), blankQuestion()].map((q) => q.key);

    expect(new Set(keys).size).toBe(keys.length);
  });

  it("counts preparation time into the candidate's total", () => {
    const template = defaultTemplate();

    // 60 + 90 + 120 answering, plus 30s preparation each.
    expect(candidateTimeSeconds(template)).toBe(270 + 3 * PREPARATION_SECONDS);
  });

  it("reports which rubric competencies no question covers", () => {
    const uncovered = uncoveredCompetencies([
      blankQuestion("technical_depth"),
    ]);

    expect(uncovered.map((option) => option.id)).toEqual([
      "system_design",
      "problem_solving",
    ]);
  });

  it("does not expect a question for the general fallback row", () => {
    expect(uncoveredCompetencies(defaultTemplate())).toEqual([]);
  });
});

describe("the editor", () => {
  it("explains that an empty list uses the default set", () => {
    render(<QuestionEditor questions={[]} onChange={() => {}} />);

    expect(
      screen.getByText(/leave this empty and the default set of three is used/i),
    ).toBeInTheDocument();
  });

  it("adds a question", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();

    render(<QuestionEditor questions={[]} onChange={onChange} />);

    await user.click(screen.getByRole("button", { name: /add question/i }));

    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({ text: "", competency: "technical_depth" }),
    ]);
  });

  it("offers the default set as a starting point", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();

    render(<QuestionEditor questions={[]} onChange={onChange} />);

    await user.click(
      screen.getByRole("button", { name: /start from the default set/i }),
    );

    expect(onChange.mock.calls[0]![0]).toHaveLength(3);
  });

  it("edits a question's text, competency and limit", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    const question = blankQuestion();

    render(
      <QuestionEditor questions={[question]} onChange={onChange} />,
    );

    // The editor is controlled, and this test holds its props still, so each
    // keystroke patches the original value. Accumulating text is covered by
    // the "creating a role with questions" case below, which re-renders.
    await user.type(screen.getByLabelText(/question 1 text/i), "W");

    expect(onChange).toHaveBeenLastCalledWith([
      expect.objectContaining({ text: "W" }),
    ]);

    await user.selectOptions(
      screen.getByLabelText(/scored as/i),
      "system_design",
    );

    expect(onChange).toHaveBeenLastCalledWith([
      expect.objectContaining({ competency: "system_design" }),
    ]);

    await user.selectOptions(screen.getByLabelText(/answer time/i), "120");

    expect(onChange).toHaveBeenLastCalledWith([
      expect.objectContaining({ time_limit_seconds: 120 }),
    ]);
  });

  it("removes a question by position", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    const template = defaultTemplate();

    render(<QuestionEditor questions={template} onChange={onChange} />);

    await user.click(
      screen.getByRole("button", { name: /remove question 2/i }),
    );

    expect(onChange).toHaveBeenCalledWith([template[0], template[2]]);
  });

  it("shows the candidate's real total, preparation included", () => {
    render(
      <QuestionEditor questions={defaultTemplate()} onChange={() => {}} />,
    );

    // 270s answering + 90s preparation = 6:00
    expect(screen.getByText(/6:00 of the candidate's time/i)).toBeInTheDocument();
    expect(screen.getByText(/including 30s preparation/i)).toBeInTheDocument();
  });

  it("warns about a rubric competency no question covers", () => {
    render(
      <QuestionEditor
        questions={[blankQuestion("technical_depth")]}
        onChange={() => {}}
      />,
    );

    expect(
      screen.getByText(/no question covers system design or problem-solving/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/weight shared across the rest/i)).toBeInTheDocument();
  });

  it("says nothing about coverage once every competency is used", () => {
    render(
      <QuestionEditor questions={defaultTemplate()} onChange={() => {}} />,
    );

    expect(screen.queryByText(/no question covers/i)).not.toBeInTheDocument();
  });
});

describe("creating a role with questions", () => {
  beforeEach(() => mockApi());

  function renderJobs() {
    return render(
      <JobsPage
        search=""
        createOpen
        onCreateOpenChange={() => {}}
        onViewCandidates={() => {}}
      />,
    );
  }

  it("sends the questions with the new role", async () => {
    const api = mockApi();
    const user = userEvent.setup();

    renderJobs();

    const dialog = screen.getByRole("dialog", { name: /create a role/i });

    await user.type(within(dialog).getByLabelText(/role title/i), "SRE");
    await user.type(
      within(dialog).getByLabelText(/description/i),
      "Keep it running",
    );

    await user.click(
      within(dialog).getByRole("button", { name: /add question/i }),
    );
    await user.type(
      within(dialog).getByLabelText(/question 1 text/i),
      "Walk us through an incident you handled.",
    );
    await user.selectOptions(
      within(dialog).getByLabelText(/answer time/i),
      "120",
    );

    await user.click(
      within(dialog).getByRole("button", { name: /create role/i }),
    );

    await waitFor(() => expect(api.createJob).toHaveBeenCalled());

    expect(api.createJob).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "SRE",
        interview_questions: [
          {
            text: "Walk us through an incident you handled.",
            competency: "technical_depth",
            time_limit_seconds: 120,
          },
        ],
      }),
    );
  });

  it("sends an empty list when none are written, so the default applies", async () => {
    const api = mockApi();
    const user = userEvent.setup();

    renderJobs();

    const dialog = screen.getByRole("dialog", { name: /create a role/i });

    await user.type(within(dialog).getByLabelText(/role title/i), "SRE");
    await user.type(within(dialog).getByLabelText(/description/i), "d");

    await user.click(
      within(dialog).getByRole("button", { name: /create role/i }),
    );

    await waitFor(() => expect(api.createJob).toHaveBeenCalled());

    expect(api.createJob).toHaveBeenCalledWith(
      expect.objectContaining({ interview_questions: [] }),
    );
  });

  it("drops a question left blank rather than sending an empty one", async () => {
    const api = mockApi();
    const user = userEvent.setup();

    renderJobs();

    const dialog = screen.getByRole("dialog", { name: /create a role/i });

    await user.type(within(dialog).getByLabelText(/role title/i), "SRE");
    await user.type(within(dialog).getByLabelText(/description/i), "d");

    // Two rows added, only one filled in.
    await user.click(
      within(dialog).getByRole("button", { name: /add question/i }),
    );
    await user.type(
      within(dialog).getByLabelText(/question 1 text/i),
      "Only this one",
    );
    await user.click(
      within(dialog).getByRole("button", { name: /add question/i }),
    );

    await user.click(
      within(dialog).getByRole("button", { name: /create role/i }),
    );

    await waitFor(() => expect(api.createJob).toHaveBeenCalled());

    const sent = api.createJob.mock.calls[0]![0] as {
      interview_questions: unknown[];
    };

    expect(sent.interview_questions).toHaveLength(1);
  });
});

describe("a role's questions on its card", () => {
  it("lists what the role actually asks", async () => {
    mockApi();

    render(
      <JobsPage
        search=""
        createOpen={false}
        onCreateOpenChange={() => {}}
        onViewCandidates={() => {}}
      />,
    );

    // The fixture job carries one question.
    expect(
      await screen.findByText("Your backend experience?"),
    ).toBeInTheDocument();
    expect(screen.getByText(/technical depth · 1:00/i)).toBeInTheDocument();
  });

  it("says when a role falls back to the default set", async () => {
    mockApi();

    render(
      <JobsPage
        search=""
        createOpen={false}
        onCreateOpenChange={() => {}}
        onViewCandidates={() => {}}
      />,
    );

    // The designer fixture has no questions of its own.
    expect(
      await screen.findByText(/uses the default set of three questions/i),
    ).toBeInTheDocument();
  });
});

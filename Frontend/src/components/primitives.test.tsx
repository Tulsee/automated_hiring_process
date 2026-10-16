/**
 * The shared building blocks, and the AI-recommendation rules they encode.
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  Avatar,
  EmptyState,
  ErrorState,
  Loading,
  Modal,
  Notice,
  ProgressBar,
  StatusPill,
} from "./primitives";
import {
  AiScoreBlock,
  EvidenceList,
  ReviewBanner,
  ScoreCell,
  WeightingDisclosure,
} from "./AiRecommendation";
import { formatDate, formatSeconds, humanise, initials } from "../lib/format";
import { flagLabel } from "../lib/flags";
import * as fixtures from "../test/fixtures";

describe("StatusPill", () => {
  it.each([
    ["received", "New applicant"],
    ["screened", "Screened"],
    ["invited_to_interview", "Invited"],
    ["invite_to_interview", "Invited"],
    ["in_progress", "In progress"],
    ["submitted", "Submitted"],
    ["completed", "Complete"],
  ])("renders %s as %s", (value, label) => {
    render(<StatusPill value={value} />);

    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("never relies on colour alone: the state is always a word", () => {
    render(<StatusPill value="submitted" />);

    expect(screen.getByText("Submitted")).toHaveClass("status");
  });

  it("falls back to a readable label for an unknown state", () => {
    render(<StatusPill value="some_new_state" />);

    expect(screen.getByText("some new state")).toBeInTheDocument();
  });

  it("shows a dash when there is no state", () => {
    render(<StatusPill value={null} />);

    expect(screen.getByText("--")).toBeInTheDocument();
  });
});

describe("ProgressBar", () => {
  it("exposes its value to assistive technology", () => {
    render(<ProgressBar value={2} max={3} label="Answers recorded" />);

    const bar = screen.getByRole("progressbar", { name: "Answers recorded" });

    expect(bar).toHaveAttribute("aria-valuenow", "2");
    expect(bar).toHaveAttribute("aria-valuemax", "3");
  });

  it("does not divide by zero", () => {
    render(<ProgressBar value={1} max={0} label="Empty" />);

    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });
});

describe("async states", () => {
  it("announces loading politely", () => {
    render(<Loading what="candidates" />);

    const status = screen.getByRole("status");

    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveTextContent(/loading candidates/i);
  });

  it("announces an error assertively and offers a retry", async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();

    render(<ErrorState error={new Error("API is down")} onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toHaveTextContent("API is down");

    await user.click(screen.getByRole("button", { name: /try again/i }));

    expect(onRetry).toHaveBeenCalled();
  });

  it("renders an empty state", () => {
    render(<EmptyState title="Nothing here">Try later</EmptyState>);

    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });
});

describe("Modal", () => {
  it("is a labelled modal dialog", () => {
    render(
      <Modal title="Create a role" onClose={() => {}}>
        body
      </Modal>,
    );

    const dialog = screen.getByRole("dialog", { name: "Create a role" });

    expect(dialog).toHaveAttribute("aria-modal", "true");
  });

  it("closes on the close button", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(
      <Modal title="X" onClose={onClose}>
        body
      </Modal>,
    );

    await user.click(screen.getByRole("button", { name: /close dialog/i }));

    expect(onClose).toHaveBeenCalled();
  });

  it("closes on a backdrop click but not on a click inside", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(
      <Modal title="X" onClose={onClose}>
        <p>inside</p>
      </Modal>,
    );

    await user.click(screen.getByText("inside"));
    expect(onClose).not.toHaveBeenCalled();

    await user.click(document.querySelector(".modal-backdrop")!);
    expect(onClose).toHaveBeenCalled();
  });
});

describe("Avatar", () => {
  it("is decorative, because the row names the person", () => {
    render(<Avatar name="Ama Boateng" />);

    expect(screen.getByText("AB")).toHaveAttribute("aria-hidden", "true");
  });
});

describe("Notice", () => {
  it("renders a title and body", () => {
    render(<Notice title="Heads up">Something to know</Notice>);

    expect(screen.getByText("Heads up")).toBeInTheDocument();
    expect(screen.getByText("Something to know")).toBeInTheDocument();
  });
});

describe("format helpers", () => {
  it.each([
    [null, "--"],
    ["not a date", "--"],
  ])("formatDate(%s) is %s", (input, expected) => {
    expect(formatDate(input)).toBe(expected);
  });

  it("formats a real date", () => {
    expect(formatDate("2026-10-14T09:00:00")).toMatch(/2026/);
  });

  it.each([
    [null, "--"],
    [0, "0:00"],
    [65, "1:05"],
    [600, "10:00"],
  ])("formatSeconds(%s) is %s", (input, expected) => {
    expect(formatSeconds(input)).toBe(expected);
  });

  it("humanises a competency key", () => {
    expect(humanise("technical_depth")).toBe("Technical depth");
    expect(humanise(null)).toBe("--");
  });

  it("builds initials from at most two names", () => {
    expect(initials("Ama Boateng")).toBe("AB");
    expect(initials("Ama Serwaa Boateng")).toBe("AS");
    expect(initials(null)).toBe("--");
  });
});

describe("flag copy", () => {
  it("explains a flag in a recruiter's words", () => {
    expect(flagLabel("empty_answer")).toMatch(/no speech was recorded/i);
    expect(flagLabel("unverified_quote")).toMatch(/could not be found/i);
  });

  it("falls back readably for an unknown flag", () => {
    expect(flagLabel("brand_new_flag")).toBe("Brand new flag");
  });
});

describe("ScoreCell", () => {
  it("spells the scale out for assistive technology", () => {
    render(<ScoreCell value={82.5} />);

    expect(screen.getByLabelText("82.5 out of 100")).toBeInTheDocument();
  });

  it("explains a missing score rather than showing a bare dash", () => {
    render(<ScoreCell value={null} />);

    expect(screen.getByTitle("Not scored yet")).toBeInTheDocument();
  });
});

describe("AiScoreBlock", () => {
  const { scorecard } = fixtures.scorecard;

  it("labels the number as a recommendation, not a decision", () => {
    render(<AiScoreBlock scorecard={scorecard} model="qwen3.5:4b" />);

    expect(screen.getByText(/ai recommendation/i)).toBeInTheDocument();
    expect(screen.getByText(/not a decision/i)).toBeInTheDocument();
    expect(screen.getByText(/you make the final call/i)).toBeInTheDocument();
  });

  it("names the model that produced it", () => {
    render(<AiScoreBlock scorecard={scorecard} model="qwen3.5:4b" />);

    expect(screen.getByText(/qwen3\.5:4b/)).toBeInTheDocument();
  });

  it("states the scale alongside the figure", () => {
    render(<AiScoreBlock scorecard={scorecard} />);

    expect(
      screen.getByLabelText("AI recommended score 2 out of 5"),
    ).toBeInTheDocument();
  });

  it("says how much of the interview it is based on", () => {
    render(<AiScoreBlock scorecard={scorecard} />);

    expect(screen.getByText(/based on 2 of 3 answers/i)).toBeInTheDocument();
  });

  it("handles an interview with no score", () => {
    render(
      <AiScoreBlock
        scorecard={{ ...scorecard, overall_score: null }}
      />,
    );

    expect(
      screen.getByLabelText("No AI score available"),
    ).toBeInTheDocument();
    expect(screen.getByText(/not enough answers/i)).toBeInTheDocument();
  });
});

describe("EvidenceList", () => {
  const { answer_scores, scorecard } = fixtures.scorecard;

  it("shows the candidate's own words for a verified score", () => {
    render(<EvidenceList scores={answer_scores} scale={scorecard.scale} />);

    expect(
      screen.getByText(/stateless services behind a load balancer/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/quote verified against the transcript/i),
    ).toBeInTheDocument();
  });

  it("says when a score has no supporting quote", () => {
    render(<EvidenceList scores={answer_scores} scale={scorecard.scale} />);

    expect(
      screen.getAllByText(/score not backed by a quote/i).length,
    ).toBeGreaterThan(0);
  });

  it("marks an unverifiable quote as not found, rather than hiding it", () => {
    render(
      <EvidenceList
        scores={[
          {
            ...answer_scores[1]!,
            evidence_quote: "I led a team of fifteen at Google",
            quote_verified: false,
            flags: ["unverified_quote"],
          },
        ]}
        scale={scorecard.scale}
      />,
    );

    expect(
      screen.getByText(/I led a team of fifteen at Google/),
    ).toBeInTheDocument();
    // Said twice on purpose: once under the quote, once as a flag chip.
    expect(
      screen.getAllByText(/could not be found in the transcript/i).length,
    ).toBe(2);
  });

  it("shows the reasoning behind each score", () => {
    render(<EvidenceList scores={answer_scores} scale={scorecard.scale} />);

    expect(
      screen.getByText(/a workable design, light on failure modes/i),
    ).toBeInTheDocument();
  });
});

describe("ReviewBanner", () => {
  it("raises an alert when the system is unsure", () => {
    render(<ReviewBanner scorecard={fixtures.scorecard.scorecard} />);

    const alert = screen.getByRole("alert");

    expect(alert).toHaveTextContent(/needs a human look/i);
    expect(alert).toHaveTextContent(/no speech was recorded/i);
  });

  it("confirms when nothing is flagged", () => {
    render(
      <ReviewBanner
        scorecard={{
          ...fixtures.scorecard.scorecard,
          needs_human_review: false,
          review_items: [],
        }}
      />,
    );

    expect(screen.getByText(/nothing flagged for review/i)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("WeightingDisclosure", () => {
  it("prints each contribution so the total can be checked by hand", async () => {
    const user = userEvent.setup();

    render(<WeightingDisclosure scorecard={fixtures.scorecard.scorecard} />);

    await user.click(screen.getByText(/how was this calculated/i));

    // 1 * 0.5 = 0.50 and 3 * 0.5 = 1.50, totalling 2
    expect(screen.getByText("0.50")).toBeInTheDocument();
    expect(screen.getByText("1.50")).toBeInTheDocument();
    expect(screen.getByText("2.00")).toBeInTheDocument();
  });

  it("names what was excluded and why it does not drag the score down", async () => {
    const user = userEvent.setup();

    render(<WeightingDisclosure scorecard={fixtures.scorecard.scorecard} />);

    await user.click(screen.getByText(/how was this calculated/i));

    expect(screen.getByText(/excluded from the total/i)).toHaveTextContent(
      /problem-solving|Problem solving/i,
    );
  });
});

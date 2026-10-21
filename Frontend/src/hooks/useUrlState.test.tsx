/**
 * Browser navigation.
 *
 * The bug these cover: navigation was `useState`, so nothing was pushed to
 * history and Back left the app instead of going back a page. A mouse's side
 * button does exactly what the toolbar's Back does, so one test for `Back`
 * covers both.
 */

import { beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import {
  DEFAULT_STATE,
  readUrlState,
  writeUrlState,
} from "./useUrlState";
import { mockApi, signedIn } from "../test/helpers";

/** Press Back the way a browser or a mouse button does. */
async function pressBack() {
  window.history.back();

  // jsdom dispatches popstate asynchronously.
  await waitFor(() => expect(true).toBe(true));
}

function nav() {
  return screen.getByRole("navigation", { name: /main navigation/i });
}

describe("reading and writing the URL", () => {
  it("defaults to the dashboard", () => {
    expect(readUrlState("")).toEqual(DEFAULT_STATE);
  });

  it("reads every navigable thing", () => {
    const state = readUrlState(
      "?view=candidates&candidate=cand-1&job=job-2&audience=applicant",
    );

    expect(state).toEqual({
      view: "candidates",
      candidate: "cand-1",
      job: "job-2",
      audience: "applicant",
    });
  });

  it("ignores a view that does not exist", () => {
    expect(readUrlState("?view=hacking").view).toBe("dashboard");
  });

  it("leaves defaults out of the URL", () => {
    const search = writeUrlState(DEFAULT_STATE, "");

    expect(search).not.toContain("view=");
    expect(search).not.toContain("audience=");
  });

  it("keeps an applicant's invite token through navigation", () => {
    // Losing the token would drop a candidate out of their own interview.
    const search = writeUrlState(
      { ...DEFAULT_STATE, view: "portal" },
      "?token=abc123",
    );

    expect(search).toContain("token=abc123");
  });

  it("round-trips", () => {
    const state = {
      view: "review" as const,
      candidate: "cand-9",
      job: "job-9",
      audience: "applicant" as const,
    };

    expect(readUrlState(writeUrlState(state, ""))).toEqual(state);
  });
});

describe("the browser's Back button", () => {
  beforeEach(() => {
    mockApi();
    signedIn();
  });

  it("puts the current page in the URL", async () => {
    const user = userEvent.setup();

    render(<App />);
    await screen.findByRole("navigation", { name: /main navigation/i });

    await user.click(within_nav(/^jobs/i));

    await waitFor(() =>
      expect(window.location.search).toContain("view=jobs"),
    );
  });

  it("goes back to the previous page", async () => {
    const user = userEvent.setup();

    render(<App />);
    await screen.findByRole("navigation", { name: /main navigation/i });

    await user.click(within_nav(/^jobs/i));
    expect(
      await screen.findByRole("heading", { name: /open.*roles/i, level: 1 }),
    ).toBeInTheDocument();

    await pressBack();

    expect(
      await screen.findByRole("heading", { name: /good to see you/i }),
    ).toBeInTheDocument();
  });

  it("walks back through several pages in order", async () => {
    const user = userEvent.setup();

    render(<App />);
    await screen.findByRole("navigation", { name: /main navigation/i });

    await user.click(within_nav(/^jobs/i));
    await screen.findByRole("heading", { name: /open.*roles/i, level: 1 });

    await user.click(within_nav(/^interviews/i));
    await screen.findByRole("heading", { name: /interview.*sessions/i, level: 1 });

    await pressBack();
    expect(
      await screen.findByRole("heading", { name: /open.*roles/i, level: 1 }),
    ).toBeInTheDocument();

    await pressBack();
    expect(
      await screen.findByRole("heading", { name: /good to see you/i }),
    ).toBeInTheDocument();
  });

  it("goes forward again", async () => {
    const user = userEvent.setup();

    render(<App />);
    await screen.findByRole("navigation", { name: /main navigation/i });

    await user.click(within_nav(/^candidates/i));
    await screen.findByRole("heading", { name: /all.*candidates/i, level: 1 });

    await pressBack();
    await screen.findByRole("heading", { name: /good to see you/i });

    window.history.forward();

    expect(
      await screen.findByRole("heading", { name: /all.*candidates/i, level: 1 }),
    ).toBeInTheDocument();
  });

  it("closes an open candidate without leaving the candidates page", async () => {
    // Opening a dialog is a navigation, so Back undoes just that.
    const user = userEvent.setup();

    render(<App />);
    await screen.findByRole("navigation", { name: /main navigation/i });

    await user.click(within_nav(/^candidates/i));
    await screen.findByRole("heading", { name: /all.*candidates/i, level: 1 });

    // The row's own button, not the row actions — those name the candidate
    // too ("Copy the interview invite link for Ama Boateng").
    await user.click(await findCandidateRow(/ama boateng/i));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(window.location.search).toContain("candidate=cand-1");

    await pressBack();

    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(
      screen.getByRole("heading", { name: /all.*candidates/i, level: 1 }),
    ).toBeInTheDocument();
  });

  it("returns to the dashboard when a candidate was opened from there", async () => {
    // That click changed page *and* opened a dialog, so it is one entry.
    const user = userEvent.setup();

    render(<App />);
    await screen.findByRole("navigation", { name: /main navigation/i });

    await user.click(
      await screen.findByRole("button", { name: /ama boateng/i }),
    );

    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    await pressBack();

    expect(
      await screen.findByRole("heading", { name: /good to see you/i }),
    ).toBeInTheDocument();
  });

  it("remembers the job filter carried from the jobs page", async () => {
    const user = userEvent.setup();

    render(<App />);
    await screen.findByRole("navigation", { name: /main navigation/i });

    await user.click(within_nav(/^jobs/i));

    const cards = await screen.findAllByRole("button", {
      name: /view candidates for/i,
    });

    await user.click(cards[0]!);

    await waitFor(() => expect(window.location.search).toContain("job=job-1"));

    await pressBack();

    expect(
      await screen.findByRole("heading", { name: /open.*roles/i, level: 1 }),
    ).toBeInTheDocument();
  });

});

describe("opening a link directly", () => {
  beforeEach(() => {
    mockApi();
    signedIn();
  });

  it("starts on the page the URL names", async () => {
    window.history.replaceState(null, "", "/?view=interviews");

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: /interview.*sessions/i, level: 1 }),
    ).toBeInTheDocument();
  });

  it("opens a candidate's dialog from a pasted link", async () => {
    window.history.replaceState(
      null,
      "",
      "/?view=candidates&candidate=cand-1",
    );

    render(<App />);

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("starts in the applicant view when asked to", async () => {
    window.history.replaceState(null, "", "/?view=portal&audience=applicant");

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: /find your next role/i }),
    ).toBeInTheDocument();
  });

  it("an invite token still bypasses the workspace", async () => {
    window.history.replaceState(null, "", "/?token=abc&view=candidates");

    render(<App />);

    // The candidate sees their interview, not a recruiter's navigation.
    expect(
      await screen.findByText(/how this works|this link does not work/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("navigation", { name: /main navigation/i }),
    ).not.toBeInTheDocument();
  });
});

/** The button that opens a candidate, as opposed to a row action. */
async function findCandidateRow(name: RegExp) {
  await screen.findByRole("heading", { level: 1 });

  const rows = document.querySelectorAll("button.candidate-name");

  for (const row of rows) {
    if (name.test(row.textContent ?? "")) return row as HTMLElement;
  }

  throw new Error(`no candidate row matching ${name}`);
}

/** The sidebar's copy of a nav label, since pages repeat some wording. */
function within_nav(name: RegExp) {
  const buttons = nav().querySelectorAll("button");

  for (const button of buttons) {
    if (name.test(button.textContent ?? "")) return button;
  }

  throw new Error(`no sidebar button matching ${name}`);
}

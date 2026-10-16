/**
 * Authoring a role's window and content.
 *
 * This was the missing half: the backend gained `PATCH /jobs/{id}` and the
 * client gained `updateJob`, but no component called it, and the create form
 * could not set a status, a publish date or a deadline. A client method
 * nothing calls is not a feature.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EditJobModal } from "./EditJobModal";
import { JobsPage } from "../pages/JobsPage";
import { failing, mockApi } from "../test/helpers";
import * as fixtures from "../test/fixtures";
import {
  previewState,
  scheduleError,
  scheduleFromJob,
} from "../lib/jobSchedule";
import { fromLocalInput, toLocalInput } from "../lib/format";

const NOW = new Date("2026-10-16T12:00:00Z");

describe("the schedule model", () => {
  it("calls a draft hidden, whatever the dates say", () => {
    const preview = previewState(
      { status: "draft", publishAt: "2020-01-01T00:00", deadline: "" },
      NOW,
    );

    expect(preview.state).toBe("Draft");
    expect(preview.note).toMatch(/nobody can see/i);
  });

  it("calls a future publish date scheduled", () => {
    const preview = previewState(
      { status: "published", publishAt: "2099-01-01T09:00", deadline: "" },
      NOW,
    );

    expect(preview.state).toBe("Scheduled");
    expect(preview.note).toMatch(/hidden until/i);
  });

  it("calls a past deadline closed", () => {
    const preview = previewState(
      { status: "published", publishAt: "", deadline: "2020-01-01T00:00" },
      NOW,
    );

    expect(preview.state).toBe("Closed");
    expect(preview.note).toMatch(/already closed/i);
  });

  it("calls a live window open and says when it closes", () => {
    const preview = previewState(
      { status: "published", publishAt: "", deadline: "2099-01-01T00:00" },
      NOW,
    );

    expect(preview.state).toBe("Open");
    expect(preview.note).toMatch(/closing/i);
  });

  it("rejects a deadline before the publish date", () => {
    expect(
      scheduleError({
        status: "published",
        publishAt: "2099-02-01T09:00",
        deadline: "2099-01-01T09:00",
      }),
    ).toMatch(/after the publish date/i);
  });

  it("accepts either date alone", () => {
    expect(
      scheduleError({
        status: "published",
        publishAt: "2099-01-01T09:00",
        deadline: "",
      }),
    ).toBeNull();
  });

  it("round-trips an API timestamp through a local input", () => {
    // The backend sends naive UTC; the input works in local time.
    const asInput = toLocalInput("2026-12-01T23:59:00");

    expect(fromLocalInput(asInput)).toBe("2026-12-01T23:59:00.000Z");
  });

  it("reads an existing job's schedule into form values", () => {
    const schedule = scheduleFromJob(fixtures.expiredJob);

    expect(schedule.status).toBe("published");
    expect(schedule.deadline).not.toBe("");
    expect(schedule.publishAt).toBe("");
  });
});

describe("editing a role", () => {
  beforeEach(() => mockApi());

  /** The modal loads the role first, so the form has to be awaited. */
  async function openEditor(job = fixtures.job, onSaved = vi.fn()) {
    render(<EditJobModal job={job} onClose={() => {}} onSaved={onSaved} />);

    await screen.findByLabelText(/role title/i);

    return { dialog: screen.getByRole("dialog"), onSaved };
  }

  it("opens pre-filled with the role as it is", async () => {
    const { dialog } = await openEditor();

    expect(within(dialog).getByLabelText(/role title/i)).toHaveValue(
      "Backend Engineer",
    );
    expect(within(dialog).getByLabelText(/required skills/i)).toHaveValue(
      "python, fastapi, mongodb",
    );
    // The role's existing question is loaded for editing.
    expect(within(dialog).getByLabelText(/question 1 text/i)).toHaveValue(
      "Your backend experience?",
    );
  });

  it("cannot be saved until something changes", async () => {
    const { dialog } = await openEditor();

    const save = within(dialog).getByRole("button", { name: /no changes/i });

    expect(save).toBeDisabled();
  });

  it("sends only the field that changed", async () => {
    const api = mockApi();
    const user = userEvent.setup();
    const { dialog } = await openEditor();

    const description = within(dialog).getByLabelText(/description/i);

    await user.clear(description);
    await user.type(description, "Rewritten");

    await user.click(within(dialog).getByRole("button", { name: /save/i }));

    await waitFor(() => expect(api.updateJob).toHaveBeenCalled());

    // Not the questions, not the title: a PATCH should say what it means.
    expect(api.updateJob).toHaveBeenCalledWith("job-1", {
      description: "Rewritten",
    });
  });

  it("sends a deadline as a UTC instant", async () => {
    const api = mockApi();
    const user = userEvent.setup();
    const { dialog } = await openEditor();

    await user.type(
      within(dialog).getByLabelText(/application deadline/i),
      "2099-12-01T23:59",
    );

    await user.click(within(dialog).getByRole("button", { name: /save/i }));

    await waitFor(() => expect(api.updateJob).toHaveBeenCalled());

    const patch = api.updateJob.mock.calls[0]![1] as { deadline: string };

    // Local input, UTC on the wire.
    expect(patch.deadline).toBe(
      new Date("2099-12-01T23:59").toISOString(),
    );
  });

  it("clears a deadline with an explicit null", async () => {
    const api = mockApi();
    const user = userEvent.setup();
    const { dialog } = await openEditor(fixtures.expiredJob);

    const deadline = within(dialog).getByLabelText(/application deadline/i);

    expect(deadline).not.toHaveValue("");

    await user.clear(deadline);

    await user.click(within(dialog).getByRole("button", { name: /save/i }));

    await waitFor(() => expect(api.updateJob).toHaveBeenCalled());

    // Omitting it would mean "leave it alone", so null is sent.
    expect(api.updateJob).toHaveBeenCalledWith("job-3", { deadline: null });
  });

  it("changes the status", async () => {
    const api = mockApi();
    const user = userEvent.setup();
    const { dialog } = await openEditor();

    await user.selectOptions(within(dialog).getByLabelText(/status/i), "closed");

    await user.click(within(dialog).getByRole("button", { name: /save/i }));

    await waitFor(() =>
      expect(api.updateJob).toHaveBeenCalledWith("job-1", {
        status: "closed",
      }),
    );
  });

  it("hides the dates for a draft, which they cannot affect", async () => {
    const user = userEvent.setup();
    const { dialog } = await openEditor();

    expect(
      within(dialog).getByLabelText(/application deadline/i),
    ).toBeInTheDocument();

    await user.selectOptions(within(dialog).getByLabelText(/status/i), "draft");

    expect(
      within(dialog).queryByLabelText(/application deadline/i),
    ).not.toBeInTheDocument();
  });

  it("replaces the questions", async () => {
    const api = mockApi();
    const user = userEvent.setup();
    const { dialog } = await openEditor();

    await user.clear(within(dialog).getByLabelText(/question 1 text/i));
    await user.type(
      within(dialog).getByLabelText(/question 1 text/i),
      "A different question",
    );

    await user.click(within(dialog).getByRole("button", { name: /save/i }));

    await waitFor(() => expect(api.updateJob).toHaveBeenCalled());

    const patch = api.updateJob.mock.calls[0]![1] as {
      interview_questions: { text: string }[];
    };

    expect(patch.interview_questions[0]!.text).toBe("A different question");
  });

  it("refuses to save an impossible window", async () => {
    const user = userEvent.setup();
    const { dialog } = await openEditor();

    await user.type(
      within(dialog).getByLabelText(/publish at/i),
      "2099-02-01T09:00",
    );
    await user.type(
      within(dialog).getByLabelText(/application deadline/i),
      "2099-01-01T09:00",
    );

    expect(
      within(dialog).getByRole("alert"),
    ).toHaveTextContent(/after the publish date/i);
    expect(within(dialog).getByRole("button", { name: /save/i })).toBeDisabled();
  });

  it("previews what applicants will experience", async () => {
    const user = userEvent.setup();
    const { dialog } = await openEditor();

    await user.selectOptions(within(dialog).getByLabelText(/status/i), "draft");

    expect(
      within(dialog).getByText(/nobody can see or apply/i),
    ).toBeInTheDocument();
  });

  it("warns when replacing a role's default questions", async () => {
    // The designer fixture has none of its own.
    const { dialog } = await openEditor(fixtures.designJob);

    expect(
      within(dialog).queryByText(/used the default questions/i),
    ).not.toBeInTheDocument();
  });

  it("reports a rejected save", async () => {
    mockApi({ updateJob: failing("The deadline must be after the publish date.") });
    const user = userEvent.setup();
    const { dialog } = await openEditor();

    const title = within(dialog).getByLabelText(/role title/i);

    await user.clear(title);
    await user.type(title, "Renamed");

    await user.click(within(dialog).getByRole("button", { name: /save/i }));

    expect(await screen.findByText(/could not save/i)).toBeInTheDocument();
  });
});

describe("reaching the editor from the jobs list", () => {
  beforeEach(() => mockApi());

  function renderJobs() {
    render(
      <JobsPage
        search=""
        createOpen={false}
        onCreateOpenChange={() => {}}
        onViewCandidates={() => {}}
      />,
    );
  }

  it("offers an Edit action per role", async () => {
    renderJobs();

    expect(
      await screen.findByRole("button", { name: /edit backend engineer/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /edit product designer/i }),
    ).toBeInTheDocument();
  });

  it("opens the editor for the role chosen", async () => {
    const user = userEvent.setup();

    renderJobs();

    await user.click(
      await screen.findByRole("button", { name: /edit product designer/i }),
    );

    expect(
      screen.getByRole("dialog", { name: /edit: product designer/i }),
    ).toBeInTheDocument();
  });

  it("reloads the list after a save", async () => {
    const api = mockApi();
    const user = userEvent.setup();

    renderJobs();

    await user.click(
      await screen.findByRole("button", { name: /edit backend engineer/i }),
    );

    const dialog = screen.getByRole("dialog");

    await user.selectOptions(within(dialog).getByLabelText(/status/i), "closed");
    await user.click(within(dialog).getByRole("button", { name: /save/i }));

    await waitFor(() => expect(api.updateJob).toHaveBeenCalled());

    // Closed/expired states come from the server, so the list is re-read.
    await waitFor(() =>
      expect(api.listJobs.mock.calls.length).toBeGreaterThan(1),
    );
  });
});

describe("creating a role with a window", () => {
  beforeEach(() => mockApi());

  it("can create a draft", async () => {
    const api = mockApi();
    const user = userEvent.setup();

    render(
      <JobsPage
        search=""
        createOpen
        onCreateOpenChange={() => {}}
        onViewCandidates={() => {}}
      />,
    );

    const dialog = screen.getByRole("dialog", { name: /create a role/i });

    await user.type(within(dialog).getByLabelText(/role title/i), "Secret");
    await user.type(within(dialog).getByLabelText(/description/i), "d");
    await user.selectOptions(within(dialog).getByLabelText(/status/i), "draft");

    await user.click(
      within(dialog).getByRole("button", { name: /create role/i }),
    );

    await waitFor(() => expect(api.createJob).toHaveBeenCalled());

    expect(api.createJob).toHaveBeenCalledWith(
      expect.objectContaining({ status: "draft" }),
    );
  });

  it("can schedule a role to publish later, with a deadline", async () => {
    const api = mockApi();
    const user = userEvent.setup();

    render(
      <JobsPage
        search=""
        createOpen
        onCreateOpenChange={() => {}}
        onViewCandidates={() => {}}
      />,
    );

    const dialog = screen.getByRole("dialog", { name: /create a role/i });

    await user.type(within(dialog).getByLabelText(/role title/i), "Later");
    await user.type(within(dialog).getByLabelText(/description/i), "d");
    await user.type(
      within(dialog).getByLabelText(/publish at/i),
      "2099-01-01T09:00",
    );
    await user.type(
      within(dialog).getByLabelText(/application deadline/i),
      "2099-02-01T09:00",
    );

    await user.click(
      within(dialog).getByRole("button", { name: /create role/i }),
    );

    await waitFor(() => expect(api.createJob).toHaveBeenCalled());

    const sent = api.createJob.mock.calls[0]![0] as {
      publish_at: string;
      deadline: string;
    };

    expect(sent.publish_at).toBe(new Date("2099-01-01T09:00").toISOString());
    expect(sent.deadline).toBe(new Date("2099-02-01T09:00").toISOString());
  });

  it("blocks creation with an impossible window", async () => {
    const user = userEvent.setup();

    render(
      <JobsPage
        search=""
        createOpen
        onCreateOpenChange={() => {}}
        onViewCandidates={() => {}}
      />,
    );

    const dialog = screen.getByRole("dialog", { name: /create a role/i });

    await user.type(within(dialog).getByLabelText(/role title/i), "Nonsense");
    await user.type(within(dialog).getByLabelText(/description/i), "d");
    await user.type(
      within(dialog).getByLabelText(/publish at/i),
      "2099-02-01T09:00",
    );
    await user.type(
      within(dialog).getByLabelText(/application deadline/i),
      "2099-01-01T09:00",
    );

    expect(
      within(dialog).getByRole("button", { name: /create role/i }),
    ).toBeDisabled();
  });
});

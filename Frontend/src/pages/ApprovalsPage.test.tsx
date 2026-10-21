/**
 * The superadmin approval queue for admin profile changes.
 */

import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApprovalsPage } from "./ApprovalsPage";
import { mockApi } from "../test/helpers";
import type { ChangeRequest } from "../types";

const request: ChangeRequest = {
  id: "cr1",
  user_id: "user-admin",
  user_name: "Al Admin",
  user_email: "admin@example.com",
  changes: {
    name: { from: "Al", to: "Alistair" },
    photo: { from: null, to: "data:image/png;base64,AAA" },
  },
  status: "pending",
  created_at: null,
  decided_by: null,
  decided_at: null,
};

describe("ApprovalsPage", () => {
  it("lists the requested changes with old and new values", async () => {
    mockApi({ listChangeRequests: async () => [request] });

    render(<ApprovalsPage />);

    expect(await screen.findByText("Alistair")).toBeInTheDocument();
    // A photo is described, not dumped as base64.
    expect(screen.getByText(/\(new photo\)/i)).toBeInTheDocument();
  });

  it("approves a request", async () => {
    const api = mockApi({ listChangeRequests: async () => [request] });
    const user = userEvent.setup();

    render(<ApprovalsPage />);

    await user.click(await screen.findByRole("button", { name: /approve/i }));

    await waitFor(() =>
      expect(api.approveChangeRequest).toHaveBeenCalledWith("cr1"),
    );
  });

  it("rejects a request", async () => {
    const api = mockApi({ listChangeRequests: async () => [request] });
    const user = userEvent.setup();

    render(<ApprovalsPage />);

    await user.click(await screen.findByRole("button", { name: /reject/i }));

    await waitFor(() =>
      expect(api.rejectChangeRequest).toHaveBeenCalledWith("cr1"),
    );
  });

  it("says when the queue is empty", async () => {
    mockApi({ listChangeRequests: async () => [] });

    render(<ApprovalsPage />);

    expect(
      await screen.findByText(/nothing to approve/i),
    ).toBeInTheDocument();
  });
});

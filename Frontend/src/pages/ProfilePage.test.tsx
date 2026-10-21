/**
 * The self-service profile: candidates edit directly; admins submit for
 * superadmin approval; everyone can change their own password.
 */

import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProfilePage } from "./ProfilePage";
import { AuthContext } from "../auth/context";
import { authValue, candidateUser, mockApi, superadminUser } from "../test/helpers";
import type { AuthUser } from "../types";

function renderProfile(user: AuthUser) {
  render(
    <AuthContext.Provider value={authValue(user)}>
      <ProfilePage />
    </AuthContext.Provider>,
  );
}

const adminUser: AuthUser = {
  ...candidateUser,
  id: "user-admin",
  email: "admin@example.com",
  name: "Al Admin",
  kind: "administration",
  role: "recruiter",
};

describe("ProfilePage", () => {
  it("lets a candidate save their details", async () => {
    const api = mockApi();
    const user = userEvent.setup();

    renderProfile(candidateUser);

    await user.clear(screen.getByLabelText(/full name/i));
    await user.type(screen.getByLabelText(/full name/i), "Casey C");
    await user.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(api.updateMyProfile).toHaveBeenCalled());
    expect(await screen.findByText(/saved/i)).toBeInTheDocument();
  });

  it("frames an admin's save as needing approval", async () => {
    mockApi({
      updateMyProfile: async () => ({
        status: "pending",
        user: null,
        request_id: "cr1",
      }),
    });
    const user = userEvent.setup();

    renderProfile(adminUser);

    // The button says so, and the result confirms it was queued.
    await user.click(screen.getByRole("button", { name: /submit for approval/i }));

    expect(
      await screen.findByText(/submitted for superadmin approval/i),
    ).toBeInTheDocument();
  });

  it("warns when a change is already pending", () => {
    mockApi();

    renderProfile({ ...adminUser, has_pending_changes: true });

    expect(
      screen.getByText(/a change is awaiting approval/i),
    ).toBeInTheDocument();
  });

  it("changes the password immediately", async () => {
    const api = mockApi();
    const user = userEvent.setup();

    renderProfile(superadminUser);

    await user.type(screen.getByLabelText(/current password/i), "old-pass-1");
    await user.type(screen.getByLabelText(/new password/i), "new-pass-123");
    await user.click(screen.getByRole("button", { name: /change password/i }));

    await waitFor(() =>
      expect(api.changeMyPassword).toHaveBeenCalledWith("old-pass-1", "new-pass-123"),
    );
  });
});

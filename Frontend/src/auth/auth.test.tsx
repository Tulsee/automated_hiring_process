/**
 * The frontend side of authentication: the login gate, what the signed-in
 * user can see, and that the token reaches the API and survives a reload.
 *
 * These render the whole <App/>, so they exercise the real AuthProvider rather
 * than the static harness other tests use.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import { setAuthToken } from "../api/client";
import {
  candidateUser,
  mockApi,
  signedIn,
  superadminUser,
} from "../test/helpers";
import type { AuthUser } from "../types";

function viewerUser(): AuthUser {
  return {
    ...superadminUser,
    id: "user-viewer",
    name: "Vee Viewer",
    is_superadmin: false,
    role: "viewer",
    permissions: ["candidates:read", "interviews:read"],
  };
}

beforeEach(() => {
  // Each test starts signed out unless it says otherwise. The admin login now
  // lives at its own URL, so land there by default; the candidate tests switch
  // to /apply. (Signed-in tests reach the workspace regardless of path.)
  setAuthToken(null);
  window.history.replaceState(null, "", "/admin");
});

describe("the login gate", () => {
  it("shows the login screen when nobody is signed in", () => {
    mockApi();

    render(<App />);

    expect(screen.getByRole("button", { name: /^sign in$/i })).toBeInTheDocument();
    // The workspace must not be reachable without signing in.
    expect(
      screen.queryByRole("navigation", { name: /main navigation/i }),
    ).not.toBeInTheDocument();
  });

  it("signs an administration user into the workspace", async () => {
    const api = mockApi();
    const user = userEvent.setup();

    render(<App />);

    await user.type(screen.getByLabelText(/email/i), "super@example.com");
    await user.type(screen.getByLabelText(/password/i), "secret123");
    await user.click(screen.getByRole("button", { name: /^sign in$/i }));

    await waitFor(() => expect(api.login).toHaveBeenCalled());

    expect(
      await screen.findByRole("navigation", { name: /main navigation/i }),
    ).toBeInTheDocument();
  });

  it("shows the sign-in error without leaving the login screen", async () => {
    mockApi({
      login: async () => {
        throw new (await import("../api/client")).ApiError(
          "Incorrect email or password",
          401,
        );
      },
    });
    const user = userEvent.setup();

    render(<App />);

    await user.type(screen.getByLabelText(/email/i), "super@example.com");
    await user.type(screen.getByLabelText(/password/i), "wrong");
    await user.click(screen.getByRole("button", { name: /^sign in$/i }));

    expect(
      await screen.findByText(/incorrect email or password/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^sign in$/i })).toBeInTheDocument();
  });

  it("registers a candidate and shows them their tracker, not the workspace", async () => {
    // Candidate sign-in / sign-up lives at /apply.
    window.history.replaceState(null, "", "/apply");
    const api = mockApi({
      register: async () => ({
        access_token: "t",
        token_type: "bearer",
        user: candidateUser,
      }),
    });
    const user = userEvent.setup();

    render(<App />);

    await user.click(
      screen.getByRole("tab", { name: /create candidate account/i }),
    );
    await user.type(screen.getByLabelText(/full name/i), "Cand");
    await user.type(screen.getByLabelText(/email/i), "cand@example.com");
    await user.type(screen.getByLabelText(/password/i), "a-good-password");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => expect(api.register).toHaveBeenCalled());

    // A candidate lands on their application tracker, with no recruiter
    // navigation — and a way through to browse and apply to open roles.
    expect(
      await screen.findByRole("heading", { name: /track every role/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /my applications/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^candidates/i }),
    ).not.toBeInTheDocument();
  });
});

describe("a restored session", () => {
  it("skips the login screen when a stored token is still good", async () => {
    mockApi();
    signedIn(superadminUser);

    render(<App />);

    // The provider confirms the token via /auth/me, then shows the workspace.
    expect(
      await screen.findByRole("navigation", { name: /main navigation/i }),
    ).toBeInTheDocument();
  });

  it("falls back to login when the stored token is rejected", async () => {
    mockApi({
      me: async () => {
        throw new (await import("../api/client")).ApiError("bad token", 401);
      },
    });
    signedIn(superadminUser);

    render(<App />);

    expect(
      await screen.findByRole("button", { name: /^sign in$/i }),
    ).toBeInTheDocument();
  });
});

describe("what a role can see", () => {
  it("hides navigation a viewer has no permission for", async () => {
    mockApi({ me: async () => viewerUser() });
    signedIn(viewerUser());

    render(<App />);

    const nav = await screen.findByRole("navigation", {
      name: /main navigation/i,
    });

    // viewer has candidates:read and interviews:read ...
    expect(nav).toHaveTextContent(/candidates/i);
    expect(nav).toHaveTextContent(/review queue/i);
    // ... but not jobs:write or the admin-only sections.
    expect(nav).not.toHaveTextContent(/^jobs$/i);
    expect(nav).not.toHaveTextContent(/access control/i);
  });

  it("shows the superadmin every section, including access control", async () => {
    mockApi();
    signedIn(superadminUser);

    render(<App />);

    const nav = await screen.findByRole("navigation", {
      name: /main navigation/i,
    });

    expect(nav).toHaveTextContent(/jobs/i);
    expect(nav).toHaveTextContent(/access control/i);
  });

  it("shows the superadmin as such in the sidebar", async () => {
    mockApi();
    signedIn(superadminUser);

    render(<App />);

    const sidebar = await screen.findByRole("navigation", {
      name: /main navigation/i,
    });

    // The role shows in the sidebar (and also in the topbar user menu), so
    // scope the assertion to the sidebar it is naming.
    expect(within(sidebar).getByText("Superadmin")).toBeInTheDocument();
  });

  it("signs out back to the login screen", async () => {
    mockApi();
    signedIn(superadminUser);
    const user = userEvent.setup();

    render(<App />);

    await user.click(
      await screen.findByRole("button", { name: /sign out/i }),
    );

    expect(
      await screen.findByRole("button", { name: /^sign in$/i }),
    ).toBeInTheDocument();
  });
});

describe("the token reaches the API", () => {
  it("sends Authorization on an authenticated request", async () => {
    // Spy on fetch underneath the real client to see the header.
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ status: "ok" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    setAuthToken("a-real-token");

    const { api } = await import("../api/client");
    await api.me();

    const init = fetchSpy.mock.calls.at(-1)![1] as RequestInit;
    expect(new Headers(init.headers).get("Authorization")).toBe(
      "Bearer a-real-token",
    );

    fetchSpy.mockRestore();
    setAuthToken(null);
  });
});

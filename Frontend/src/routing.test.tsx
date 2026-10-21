/**
 * The public entry points: a signed-out visitor sees the job board, and the
 * two login URLs show the right sign-in.
 */

import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "./App";
import { mockApi } from "./test/helpers";
import { setAuthToken } from "./api/client";

beforeEach(() => {
  setAuthToken(null);
  localStorage.clear();
});

describe("the public entry points", () => {
  it("shows the job board to a signed-out visitor at the root", async () => {
    window.history.replaceState(null, "", "/");
    mockApi();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: /find your next role/i }),
    ).toBeInTheDocument();
    // Browsing needs no account; applying sends them to sign in.
    expect(
      screen.getByRole("button", { name: /candidate sign in/i }),
    ).toBeInTheDocument();
    // No workspace, no login form on the public board.
    expect(
      screen.queryByRole("navigation", { name: /main navigation/i }),
    ).not.toBeInTheDocument();
  });

  it("shows an admin-only sign-in at /admin", async () => {
    window.history.replaceState(null, "", "/admin");
    mockApi();

    render(<App />);

    expect(
      await screen.findByText(/hiring team sign-in/i),
    ).toBeInTheDocument();
    // Admins cannot self-register, so there is no create-account tab.
    expect(
      screen.queryByRole("tab", { name: /create candidate account/i }),
    ).not.toBeInTheDocument();
  });

  it("offers candidate sign-up at /apply", async () => {
    window.history.replaceState(null, "", "/apply");
    mockApi();

    render(<App />);

    expect(
      await screen.findByRole("tab", { name: /create candidate account/i }),
    ).toBeInTheDocument();
  });
});

/**
 * The topbar user menu shows the real signed-in account (the bug it fixes was
 * a hardcoded name there) and signs the user out from a dropdown.
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { UserMenu } from "./UserMenu";
import { AuthContext } from "../auth/context";
import { authValue, candidateUser, superadminUser } from "../test/helpers";

function renderMenu(user = superadminUser, signOut = vi.fn()) {
  render(
    <AuthContext.Provider value={{ ...authValue(user), signOut }}>
      <UserMenu />
    </AuthContext.Provider>,
  );
  return { signOut };
}

describe("UserMenu", () => {
  it("shows the signed-in user, not a hardcoded name", () => {
    renderMenu(superadminUser);

    expect(screen.getByText(superadminUser.name)).toBeInTheDocument();
    // The role label, so the topbar matches the sidebar.
    expect(screen.getByText("Superadmin")).toBeInTheDocument();
  });

  it("labels a candidate as a candidate", () => {
    // A distinct name, so the role label isn't confused with the name.
    renderMenu({ ...candidateUser, name: "Riya Sharma" });

    expect(screen.getByText("Riya Sharma")).toBeInTheDocument();
    expect(screen.getByText("Candidate")).toBeInTheDocument();
  });

  it("opens a dropdown and signs out", async () => {
    const user = userEvent.setup();
    const { signOut } = renderMenu(superadminUser);

    // Closed until clicked.
    expect(
      screen.queryByRole("menuitem", { name: /sign out/i }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /super admin/i }));

    const menu = screen.getByRole("menu");
    expect(within(menu).getByText(superadminUser.email)).toBeInTheDocument();

    await user.click(within(menu).getByRole("menuitem", { name: /sign out/i }));

    expect(signOut).toHaveBeenCalledOnce();
  });

  it("renders nothing when signed out", () => {
    const { container } = render(
      <AuthContext.Provider value={authValue(null)}>
        <UserMenu />
      </AuthContext.Provider>,
    );

    expect(container).toBeEmptyDOMElement();
  });
});

/**
 * Theme and text-size switching.
 *
 * These assert the behaviour that was reported broken: that the control is
 * reachable at all, and that choosing a theme actually reaches
 * `document.documentElement`, which is what the stylesheet keys off.
 */

import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AppShell } from "./AppShell";
import { THEMES, TEXT_SIZES } from "../hooks/useTheme";
import { AuthHarness } from "../test/helpers";

function renderShell() {
  return render(
    <AuthHarness>
      <AppShell
        view="dashboard"
        onNavigate={() => {}}
        audience="recruiter"
        search=""
        onSearchChange={() => {}}
      >
        <p>content</p>
      </AppShell>
    </AuthHarness>,
  );
}

async function openMenu() {
  const user = userEvent.setup();

  await user.click(screen.getByRole("button", { name: /appearance/i }));

  return user;
}

describe("the appearance control exists", () => {
  it("lives in the sidebar, not the topbar", () => {
    renderShell();

    const trigger = screen.getByRole("button", { name: /appearance/i });

    expect(trigger).toBeInTheDocument();

    const nav = screen.getByRole("navigation", { name: /main navigation/i });

    expect(nav).toContainElement(trigger);

    // The topbar must no longer carry it.
    const topbar = document.querySelector(".topbar")!;
    expect(topbar).not.toContainElement(trigger);
  });

  it("opens upward, because the trigger sits at the bottom of the sidebar", async () => {
    renderShell();
    await openMenu();

    expect(document.querySelector(".appearance--sidebar")).toBeTruthy();
  });

  it("is closed until opened", () => {
    renderShell();

    const trigger = screen.getByRole("button", { name: /appearance/i });

    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument();
  });

  it("opens a theme radiogroup", async () => {
    renderShell();
    await openMenu();

    expect(screen.getByRole("radiogroup")).toBeInTheDocument();
    expect(screen.getAllByRole("radio")).toHaveLength(THEMES.length);
  });

  it("offers every theme by name", async () => {
    renderShell();
    await openMenu();

    for (const theme of THEMES) {
      expect(
        screen.getByRole("radio", { name: new RegExp(theme.label, "i") }),
      ).toBeInTheDocument();
    }
  });
});

describe("choosing a theme", () => {
  it("writes data-theme onto the document", async () => {
    renderShell();
    const user = await openMenu();

    await user.click(screen.getByRole("radio", { name: /dark/i }));

    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  });

  it.each(["dark", "midnight", "warm", "contrast"] as const)(
    "applies the %s theme",
    async (theme) => {
      renderShell();
      const user = await openMenu();

      const label = THEMES.find((entry) => entry.id === theme)!.label;

      await user.click(screen.getByRole("radio", { name: new RegExp(label, "i") }));

      expect(document.documentElement).toHaveAttribute("data-theme", theme);
    },
  );

  it("marks the active theme as checked", async () => {
    renderShell();
    const user = await openMenu();

    await user.click(screen.getByRole("radio", { name: /midnight/i }));

    expect(screen.getByRole("radio", { name: /midnight/i })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.getByRole("radio", { name: /^light/i })).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });

  it("removes data-theme for System, so the OS preference applies", async () => {
    renderShell();
    const user = await openMenu();

    await user.click(screen.getByRole("radio", { name: /dark/i }));
    expect(document.documentElement).toHaveAttribute("data-theme");

    await user.click(screen.getByRole("radio", { name: /system/i }));
    expect(document.documentElement).not.toHaveAttribute("data-theme");
  });

  it("persists the choice", async () => {
    renderShell();
    const user = await openMenu();

    await user.click(screen.getByRole("radio", { name: /warm/i }));

    expect(localStorage.getItem("hirewise.theme")).toBe("warm");
  });

  it("restores a persisted choice on mount", () => {
    localStorage.setItem("hirewise.theme", "contrast");

    renderShell();

    expect(document.documentElement).toHaveAttribute("data-theme", "contrast");
  });

  it("ignores a stored value that is not a real theme", () => {
    localStorage.setItem("hirewise.theme", "neon-disco");

    renderShell();

    // Falls back to the default theme (warm), not the invalid stored value.
    expect(document.documentElement).toHaveAttribute("data-theme", "warm");
  });
});

describe("text size", () => {
  it("offers every size", async () => {
    renderShell();
    await openMenu();

    const group = screen.getByRole("group", { name: /text size/i });

    for (const size of TEXT_SIZES) {
      expect(
        within(group).getByRole("button", { name: size.label }),
      ).toBeInTheDocument();
    }
  });

  it("defaults to 1.15, because the base sizes are too small", () => {
    renderShell();

    expect(
      document.documentElement.style.getPropertyValue("--font-scale"),
    ).toBe("1.15");
  });

  it.each([
    ["Compact", "1"],
    ["Large", "1.3"],
    ["Larger", "1.45"],
  ])("sets --font-scale for %s", async (label, expected) => {
    renderShell();
    const user = await openMenu();

    await user.click(screen.getByRole("button", { name: label }));

    expect(
      document.documentElement.style.getPropertyValue("--font-scale"),
    ).toBe(expected);
  });

  it("marks the active size as pressed", async () => {
    renderShell();
    const user = await openMenu();

    await user.click(screen.getByRole("button", { name: "Large" }));

    expect(screen.getByRole("button", { name: "Large" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("persists the choice", async () => {
    renderShell();
    const user = await openMenu();

    await user.click(screen.getByRole("button", { name: "Larger" }));

    expect(localStorage.getItem("hirewise.textSize")).toBe("larger");
  });
});

describe("dismissing the menu", () => {
  it("closes on Escape", async () => {
    renderShell();
    const user = await openMenu();

    expect(screen.getByRole("radiogroup")).toBeInTheDocument();

    await user.keyboard("{Escape}");

    expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument();
  });

  it("closes on an outside click", async () => {
    renderShell();
    const user = await openMenu();

    await user.click(screen.getByText("content"));

    expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument();
  });

  it("stays open when clicking inside it", async () => {
    renderShell();
    const user = await openMenu();

    await user.click(screen.getByRole("radio", { name: /dark/i }));

    expect(screen.getByRole("radiogroup")).toBeInTheDocument();
  });
});

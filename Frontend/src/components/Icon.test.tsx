/**
 * The icon set, and the sidebar controls that use it.
 *
 * The test that matters here is the duplicate-geometry one: `settings` was
 * drawn as a circle with eight radiating ticks, which is a sun, so it was
 * indistinguishable from the `sun` icon sitting next to it in the sidebar.
 * Two controls that look identical are a usability bug a type checker cannot
 * catch.
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Icon, type IconName } from "./Icon";
import { AppShell } from "./AppShell";
import { AuthHarness } from "../test/helpers";

/** Reduce a path to its shape: commands and rounded coordinates. */
function geometry(path: string): string {
  return path
    .replace(/[\d.]+/g, (n) => String(Math.round(Number(n) * 2) / 2))
    .replace(/\s+/g, " ")
    .trim();
}

function pathOf(name: IconName): string {
  const { container } = render(<Icon name={name} />);

  return container.querySelector("path")!.getAttribute("d")!;
}

const NAMES: IconName[] = [
  "search",
  "bell",
  "settings",
  "help",
  "menu",
  "close",
  "chevron-right",
  "chevron-down",
  "chevron-up",
  "arrow-right",
  "users",
  "briefcase",
  "clipboard",
  "calendar",
  "sparkles",
  "plus",
  "info",
  "check",
  "alert",
  "upload",
  "play",
  "clock",
  "pin",
  "trending",
  "file",
  "quote",
  "mic",
  "external",
  "sun",
];

describe("the icon set", () => {
  it("draws every name", () => {
    for (const name of NAMES) {
      expect(pathOf(name), name).toBeTruthy();
    }
  });

  it("gives no two icons the same geometry", () => {
    const seen = new Map<string, IconName>();
    const clashes: string[] = [];

    for (const name of NAMES) {
      const shape = geometry(pathOf(name));

      const existing = seen.get(shape);

      if (existing) {
        clashes.push(`${existing} and ${name}`);
      } else {
        seen.set(shape, name);
      }
    }

    expect(clashes).toEqual([]);
  });

  it("does not draw settings as a sun", () => {
    // Both were a circle plus eight radial ticks. A gear has an outline with
    // teeth, so it has far more curve commands than a sun's straight rays.
    const settings = pathOf("settings");
    const sun = pathOf("sun");

    const rays = (path: string) => (path.match(/M[\d.]+ [\d.]+[vhl]/g) ?? []).length;

    expect(rays(sun)).toBeGreaterThan(4);
    expect(rays(settings)).toBe(0);
    expect(geometry(settings)).not.toBe(geometry(sun));
  });

  it("is decorative unless given a title", () => {
    const { container } = render(<Icon name="search" />);

    expect(container.querySelector("svg")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
  });

  it("becomes an image with an accessible name when titled", () => {
    render(<Icon name="search" title="Search" />);

    expect(screen.getByRole("img", { name: "Search" })).toBeInTheDocument();
  });
});

describe("the sidebar's controls", () => {
  function renderShell() {
    render(
      <AuthHarness>
        <AppShell
          view="dashboard"
          onNavigate={() => {}}
          audience="recruiter"
          onAudienceChange={() => {}}
          search=""
          onSearchChange={() => {}}
        >
          <p>content</p>
        </AppShell>
      </AuthHarness>,
    );

    return screen.getByRole("navigation", { name: /main navigation/i });
  }

  it("has exactly one icon-only control in the account row", () => {
    renderShell();

    const row = document.querySelector(".sidebar-user")!;

    const controls = row.querySelectorAll("button");

    // Appearance (a menu) and sign out.
    expect(controls).toHaveLength(2);
    expect(controls[0]!).toHaveAttribute("aria-haspopup", "true");
  });

  it("no longer offers a settings button with nothing behind it", () => {
    renderShell();

    expect(
      screen.queryByRole("button", { name: /account settings/i }),
    ).not.toBeInTheDocument();
  });

  it("gives every sidebar control a distinct accessible name", () => {
    const nav = renderShell();

    const names = [...nav.querySelectorAll("button")].map((button) => {
      const svgLabel = button
        .querySelector("svg")
        ?.getAttribute("aria-label");

      return (button.textContent?.trim() || svgLabel || "?").toLowerCase();
    });

    expect(new Set(names).size).toBe(names.length);
  });
});

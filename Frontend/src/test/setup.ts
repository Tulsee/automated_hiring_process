import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

beforeEach(() => {
  // Theme and text size persist to localStorage and to <html>; each test
  // starts from a clean slate so one cannot leak into the next.
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.style.removeProperty("--font-scale");
});

// jsdom has no matchMedia, which the theme code and the stylesheet's
// prefers-color-scheme handling both touch.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

/**
 * jsdom does not implement form submission, so clicking a `type="submit"`
 * button never dispatches a `submit` event — verified with a plain form and no
 * React involved. Without this bridge, every form in the app would look broken
 * under test while working in a browser.
 *
 * Constraint validation is deliberately not consulted: jsdom reports
 * `valueMissing: true` for a file input even when a file is attached, which
 * would block every resume upload. The app guards submission by disabling the
 * button instead, and that is asserted on its own.
 */
document.addEventListener("click", (event) => {
  const target = event.target as HTMLElement | null;

  const button = target?.closest?.(
    "button[type=submit], input[type=submit]",
  ) as HTMLButtonElement | null;

  if (!button || button.disabled) return;

  const form = button.form ?? button.closest("form");

  if (!form) return;

  form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
});

/**
 * Navigation, the shell's chrome, and the data hook every page depends on.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  act,
  render,
  renderHook,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { useApi, useAction } from "./hooks/useApi";
import { mockApi, pending } from "./test/helpers";

describe("navigating the app", () => {
  beforeEach(() => mockApi());

  it("opens on the dashboard", async () => {
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: /good to see you/i }),
    ).toBeInTheDocument();
  });

  it("marks the current page in the navigation", async () => {
    render(<App />);

    expect(
      screen.getByRole("button", { name: /^dashboard/i }),
    ).toHaveAttribute("aria-current", "page");
  });

  it.each([
    [/^jobs/i, /open.*roles/i],
    [/^candidates/i, /all.*candidates/i],
    [/review queue/i, /interview.*review/i],
    [/^interviews/i, /interview.*sessions/i],
  ])("navigates to %s", async (navLabel, headingPattern) => {
    const user = userEvent.setup();

    render(<App />);

    // Scoped to the sidebar: the dashboard also has an "Open review queue"
    // button, which is a different control.
    const nav = screen.getByRole("navigation", { name: /main navigation/i });

    await user.click(within(nav).getByRole("button", { name: navLabel }));

    expect(
      await screen.findByRole("heading", { name: headingPattern, level: 1 }),
    ).toBeInTheDocument();
  });

  it("switches to the applicant view and back", async () => {
    const user = userEvent.setup();

    render(<App />);

    await user.click(screen.getByRole("button", { name: /switch view/i }));

    expect(
      await screen.findByRole("heading", { name: /find your next role/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/candidate view/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /switch view/i }));

    expect(
      await screen.findByRole("heading", { name: /good to see you/i }),
    ).toBeInTheDocument();
  });

  it("carries a job filter from Jobs into Candidates", async () => {
    const api = mockApi();
    const user = userEvent.setup();

    render(<App />);

    await user.click(screen.getByRole("button", { name: /^jobs/i }));

    const buttons = await screen.findAllByRole("button", {
      name: /view candidates for/i,
    });

    await user.click(buttons[0]!);

    await waitFor(() =>
      expect(api.listCandidates).toHaveBeenCalledWith(
        expect.objectContaining({ job_id: "job-1" }),
      ),
    );
  });

  it("opens a candidate from the dashboard table", async () => {
    const user = userEvent.setup();

    render(<App />);

    await user.click(
      await screen.findByRole("button", { name: /ama boateng/i }),
    );

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("clears the search box when changing page", async () => {
    const user = userEvent.setup();

    render(<App />);

    const search = screen.getByLabelText(/search candidates and roles/i);

    await user.type(search, "ama");
    expect(search).toHaveValue("ama");

    await user.click(screen.getByRole("button", { name: /^jobs/i }));

    expect(search).toHaveValue("");
  });
});

describe("the shell's chrome", () => {
  beforeEach(() => mockApi());

  it("offers a skip link to the content", () => {
    render(<App />);

    expect(
      screen.getByRole("link", { name: /skip to main content/i }),
    ).toHaveAttribute("href", "#main");
  });

  it("focuses search on the advertised / shortcut", async () => {
    const user = userEvent.setup();

    render(<App />);

    await user.keyboard("/");

    expect(screen.getByLabelText(/search candidates and roles/i)).toHaveFocus();
  });

  it("does not hijack / while typing in a field", async () => {
    const user = userEvent.setup();

    render(<App />);

    const search = screen.getByLabelText(/search candidates and roles/i);

    await user.click(search);
    await user.keyboard("a/b");

    expect(search).toHaveValue("a/b");
  });
});

describe("useApi", () => {
  it("reports loading, then the data", async () => {
    const { result } = renderHook(() => useApi(async () => "value", []));

    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toBe("value");
    expect(result.current.error).toBeNull();
  });

  it("stays loading while the request is in flight", () => {
    const { result } = renderHook(() => useApi(pending<string>, []));

    expect(result.current.loading).toBe(true);
  });

  it("captures an error without throwing", async () => {
    const { result } = renderHook(() =>
      useApi(async () => {
        throw new Error("boom");
      }, []),
    );

    await waitFor(() => expect(result.current.error).not.toBeNull());

    expect(result.current.error?.message).toBe("boom");
    expect(result.current.loading).toBe(false);
  });

  it("refetches when a dependency changes", async () => {
    const fetcher = vi.fn(async (id: string) => id);

    const { result, rerender } = renderHook(
      ({ id }: { id: string }) => useApi(() => fetcher(id), [id]),
      { initialProps: { id: "a" } },
    );

    await waitFor(() => expect(result.current.data).toBe("a"));

    rerender({ id: "b" });

    await waitFor(() => expect(result.current.data).toBe("b"));

    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("refetches on reload()", async () => {
    const fetcher = vi.fn(async () => "x");

    const { result } = renderHook(() => useApi(fetcher, []));

    await waitFor(() => expect(result.current.data).toBe("x"));

    act(() => result.current.reload());

    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  });

  it("discards a response that arrives after the inputs changed", async () => {
    // The slow first request resolves last; its result must not win.
    const fetcher = (id: string) =>
      new Promise<string>((resolve) =>
        setTimeout(() => resolve(id), id === "a" ? 50 : 1),
      );

    const { result, rerender } = renderHook(
      ({ id }: { id: string }) => useApi(() => fetcher(id), [id]),
      { initialProps: { id: "a" } },
    );

    rerender({ id: "b" });

    await waitFor(() => expect(result.current.data).toBe("b"));

    // Give the stale request time to land.
    await new Promise((resolve) => setTimeout(resolve, 80));

    expect(result.current.data).toBe("b");
  });
});

describe("useAction", () => {
  it("tracks pending state around the call", async () => {
    const { result } = renderHook(() =>
      useAction(async (value: string) => value.toUpperCase()),
    );

    expect(result.current.pending).toBe(false);

    let outcome: string | null = null;

    await act(async () => {
      outcome = await result.current.run("ok");
    });

    expect(outcome).toBe("OK");
    expect(result.current.pending).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("returns null and records the error on failure", async () => {
    const { result } = renderHook(() =>
      useAction(async () => {
        throw new Error("rejected");
      }),
    );

    let outcome: unknown = "unset";

    await act(async () => {
      outcome = await result.current.run();
    });

    expect(outcome).toBeNull();
    expect(result.current.error?.message).toBe("rejected");
  });

  it("clears a previous error on the next attempt", async () => {
    let shouldFail = true;

    const { result } = renderHook(() =>
      useAction(async () => {
        if (shouldFail) throw new Error("first");
        return "second";
      }),
    );

    await act(async () => {
      await result.current.run();
    });

    expect(result.current.error).not.toBeNull();

    shouldFail = false;

    await act(async () => {
      await result.current.run();
    });

    expect(result.current.error).toBeNull();
  });
});

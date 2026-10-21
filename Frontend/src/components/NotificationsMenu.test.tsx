/**
 * The topbar bell: shows unread notifications and lets the user clear them.
 */

import { describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NotificationsMenu } from "./NotificationsMenu";
import { mockApi } from "../test/helpers";

const feed = {
  unread: 2,
  notifications: [
    {
      id: "n1",
      kind: "application",
      title: "You're invited to interview",
      body: "Backend Engineer",
      link: null,
      read: false,
      created_at: new Date().toISOString(),
    },
    {
      id: "n2",
      kind: "application",
      title: "Application received",
      body: "",
      link: null,
      read: true,
      created_at: new Date().toISOString(),
    },
  ],
};

describe("NotificationsMenu", () => {
  it("shows an unread marker from the feed", async () => {
    mockApi({ listNotifications: async () => feed });

    render(<NotificationsMenu />);

    expect(
      await screen.findByRole("button", { name: /notifications, 2 unread/i }),
    ).toBeInTheDocument();
  });

  it("opens the panel and lists notifications", async () => {
    mockApi({ listNotifications: async () => feed });
    const user = userEvent.setup();

    render(<NotificationsMenu />);

    await user.click(
      await screen.findByRole("button", { name: /notifications/i }),
    );

    const menu = screen.getByRole("menu");
    expect(
      within(menu).getByText(/you're invited to interview/i),
    ).toBeInTheDocument();
  });

  it("marks one read when clicked", async () => {
    const api = mockApi({ listNotifications: async () => feed });
    const user = userEvent.setup();

    render(<NotificationsMenu />);

    await user.click(
      await screen.findByRole("button", { name: /notifications/i }),
    );
    await user.click(
      screen.getByRole("button", { name: /you're invited to interview/i }),
    );

    await waitFor(() =>
      expect(api.markNotificationRead).toHaveBeenCalledWith("n1"),
    );
  });

  it("marks all read", async () => {
    const api = mockApi({ listNotifications: async () => feed });
    const user = userEvent.setup();

    render(<NotificationsMenu />);

    await user.click(
      await screen.findByRole("button", { name: /notifications/i }),
    );
    await user.click(screen.getByRole("button", { name: /mark all read/i }));

    await waitFor(() =>
      expect(api.markAllNotificationsRead).toHaveBeenCalled(),
    );
  });

  it("says so when there is nothing", async () => {
    mockApi({ listNotifications: async () => ({ unread: 0, notifications: [] }) });
    const user = userEvent.setup();

    render(<NotificationsMenu />);

    await user.click(
      await screen.findByRole("button", { name: /notifications/i }),
    );

    expect(screen.getByText(/all caught up/i)).toBeInTheDocument();
  });
});

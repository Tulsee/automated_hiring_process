/**
 * The topbar bell: a dropdown of the signed-in user's notifications.
 *
 * The feed is fetched on mount (so the unread dot is right straight away) and
 * refreshed each time the panel opens. Clicking one marks it read; a "Mark all
 * read" button clears the lot — so the dot reflects what the person has not yet
 * acknowledged.
 */

import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { Icon } from "./Icon";
import type { AppNotification } from "../types";

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function NotificationsMenu() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AppNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  async function load() {
    try {
      const feed = await api.listNotifications();
      setItems(feed.notifications);
      setUnread(feed.unread);
    } catch {
      // A failed poll should not break the shell; leave the last feed in place.
    }
  }

  // Fetch once on mount so the dot is accurate before the bell is ever opened.
  // The setState lives in the async callback (not the effect body) so it does
  // not trigger a cascading render.
  useEffect(() => {
    let active = true;

    api
      .listNotifications()
      .then((feed) => {
        if (!active) return;
        setItems(feed.notifications);
        setUnread(feed.unread);
      })
      .catch(() => {
        // A failed initial fetch leaves an empty, dot-less bell.
      });

    return () => {
      active = false;
    };
  }, []);

  // Outside-click and Escape to close, like the user menu.
  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next) await load();
  }

  async function readOne(id: string) {
    setItems((current) =>
      current.map((n) => (n.id === id ? { ...n, read: true } : n)),
    );
    setUnread((count) => Math.max(0, count - 1));
    try {
      await api.markNotificationRead(id);
    } catch {
      // A failed mark is recovered by the next load.
    }
  }

  async function readAll() {
    setItems((current) => current.map((n) => ({ ...n, read: true })));
    setUnread(0);
    try {
      await api.markAllNotificationsRead();
    } catch {
      // A failed mark is recovered by the next load.
    }
  }

  return (
    <div className="notif-menu" ref={containerRef}>
      <button
        type="button"
        ref={triggerRef}
        className="icon-button notification-button"
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={
          unread > 0 ? `Notifications, ${unread} unread` : "Notifications"
        }
        onClick={toggle}
      >
        <Icon name="bell" size={17} title="Notifications" />
        {unread > 0 ? <i aria-hidden="true" /> : null}
      </button>

      {open ? (
        <div className="notif-panel" role="menu">
          <div className="notif-head">
            <strong>Notifications</strong>
            {items.some((n) => !n.read) ? (
              <button type="button" className="text-button" onClick={readAll}>
                Mark all read
              </button>
            ) : null}
          </div>

          {items.length === 0 ? (
            <p className="notif-empty">You're all caught up.</p>
          ) : (
            <ul className="notif-list">
              {items.map((notification) => (
                <li
                  key={notification.id}
                  className={`notif-item ${notification.read ? "" : "is-unread"}`.trim()}
                >
                  <button
                    type="button"
                    className="notif-item-button"
                    onClick={() => readOne(notification.id)}
                  >
                    <strong>{notification.title}</strong>
                    {notification.body ? <p>{notification.body}</p> : null}
                    <small>{timeAgo(notification.created_at)}</small>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}

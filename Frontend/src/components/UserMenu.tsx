/**
 * The signed-in user in the topbar, with a dropdown that signs them out.
 *
 * Shows the real account — the topbar used to carry a hardcoded name while the
 * sidebar already showed the real one, which is the mismatch this fixes.
 */

import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/context";
import { Avatar } from "./primitives";
import { Icon } from "./Icon";

export function UserMenu() {
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

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

  if (!user) return null;

  const roleLabel = user.is_superadmin
    ? "Superadmin"
    : user.kind === "candidate"
      ? "Candidate"
      : user.role ?? "No role";

  return (
    <div className="user-menu" ref={containerRef}>
      <button
        type="button"
        className="user-menu-trigger"
        ref={triggerRef}
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Avatar name={user.name} variant="profile" />
        <span className="topbar-user">
          <strong>{user.name}</strong>
          <small>{roleLabel}</small>
        </span>
        <Icon name={open ? "chevron-up" : "chevron-down"} size={14} />
      </button>

      {open ? (
        <div className="user-menu-panel" role="menu">
          <div className="user-menu-head">
            <strong>{user.name}</strong>
            <small>{user.email}</small>
            <span className="user-menu-role">{roleLabel}</span>
          </div>
          <button
            type="button"
            role="menuitem"
            className="user-menu-item"
            onClick={() => {
              setOpen(false);
              signOut();
            }}
          >
            <Icon name="external" size={14} />
            Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}

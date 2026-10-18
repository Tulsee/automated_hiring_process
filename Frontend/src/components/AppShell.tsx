/**
 * The frame every page sits in: sidebar, topbar, content, footer.
 *
 * Navigation is button-driven state rather than a router, which is what the
 * stylesheet's `.nav-item` (a <button>) is built for. The trade-off is no
 * deep-linkable URLs; see the README.
 */

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Icon } from "./Icon";
import { Avatar } from "./primitives";
import {
  APPLICANT_NAV,
  RECRUITER_NAV,
  visibleNav,
  type ViewId,
} from "../lib/nav";
import { useAuth } from "../auth/context";
import { AppearanceMenu } from "./AppearanceMenu";
import { useTheme } from "../hooks/useTheme";
import { ApiStatus } from "./ApiStatus";
import { UserMenu } from "./UserMenu";


interface AppShellProps {
  view: ViewId;
  onNavigate: (view: ViewId) => void;
  audience: "recruiter" | "applicant";
  onAudienceChange: (audience: "recruiter" | "applicant") => void;
  counts?: Partial<Record<ViewId, number>>;
  search: string;
  onSearchChange: (value: string) => void;
  children: ReactNode;
}

export function AppShell({
  view,
  onNavigate,
  audience,
  onAudienceChange,
  counts = {},
  search,
  onSearchChange,
  children,
}: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  const { theme, setTheme, textSize, setTextSize } = useTheme();
  const { user, can, signOut, isAdministration } = useAuth();

  const nav =
    audience === "recruiter"
      ? visibleNav(RECRUITER_NAV, can)
      : APPLICANT_NAV;

  // The topbar advertises "/" as the search shortcut, so it has to work.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const typing =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement;

      if (event.key === "/" && !typing) {
        event.preventDefault();
        searchRef.current?.focus();
      }

      if (event.key === "Escape") setSidebarOpen(false);
    }

    window.addEventListener("keydown", onKeyDown);

    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <div className="app-shell">
      <a href="#main" className="sr-only">
        Skip to main content
      </a>

      <nav
        className={`sidebar ${sidebarOpen ? "sidebar--open" : ""}`.trim()}
        aria-label="Main navigation"
      >
        <div className="brand">
          <span className="brand-mark">
            <Icon name="sparkles" size={18} />
          </span>
          <span>
            <strong>Hirewise</strong>
            <small>AI recruitment</small>
          </span>
          <button
            type="button"
            className="icon-button sidebar-close"
            onClick={() => setSidebarOpen(false)}
          >
            <Icon name="close" size={16} title="Close navigation" />
          </button>
        </div>

        <p className="workspace-label">
          {audience === "recruiter" ? "RECRUITER WORKSPACE" : "CANDIDATE VIEW"}
        </p>

        <div className="side-nav">
          {nav.map((entry) => {
            const active = entry.id === view;

            return (
              <button
                key={entry.id}
                type="button"
                className={`nav-item ${active ? "nav-item--active" : ""}`.trim()}
                aria-current={active ? "page" : undefined}
                onClick={() => {
                  onNavigate(entry.id);
                  setSidebarOpen(false);
                }}
              >
                <Icon name={entry.icon} size={16} />
                {entry.label}
                {counts[entry.id] ? (
                  <span className="nav-count">{counts[entry.id]}</span>
                ) : null}
              </button>
            );
          })}
        </div>

        <div className="sidebar-spacer" />

        {isAdministration ? (
          <div className="sidebar-help">
            <span className="help-icon">
              <Icon name="users" size={16} />
            </span>
            <strong>
              {audience === "recruiter" ? "See the candidate view" : "Back to hiring"}
            </strong>
            <p>
              {audience === "recruiter"
                ? "Open the applicant-facing portal to check what candidates see."
                : "Return to the recruiter workspace."}
            </p>
            <button
              type="button"
              onClick={() =>
                onAudienceChange(
                  audience === "recruiter" ? "applicant" : "recruiter",
                )
              }
            >
              Switch view <Icon name="arrow-right" size={12} />
            </button>
          </div>
        ) : null}

        <div className="sidebar-user">
          <Avatar name={user?.name ?? "You"} variant="sidebar" />
          <span>
            <strong>{user?.name ?? "You"}</strong>
            <small>
              {user?.is_superadmin
                ? "Superadmin"
                : user?.role
                  ? user.role
                  : user?.kind === "candidate"
                    ? "Candidate"
                    : "No role"}
            </small>
          </span>
          <AppearanceMenu
            theme={theme}
            onThemeChange={setTheme}
            textSize={textSize}
            onTextSizeChange={setTextSize}
            placement="sidebar"
          />
          <button
            type="button"
            className="icon-button"
            onClick={signOut}
          >
            <Icon name="external" size={15} title="Sign out" />
          </button>
        </div>
      </nav>

      {sidebarOpen ? (
        <button
          type="button"
          className="mobile-scrim"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
        />
      ) : null}

      <div className="main-area">
        <header className="topbar">
          <button
            type="button"
            className="icon-button mobile-menu"
            onClick={() => setSidebarOpen(true)}
          >
            <Icon name="menu" size={18} title="Open navigation" />
          </button>

          <div className="global-search">
            <Icon name="search" size={15} />
            <label htmlFor="global-search" className="sr-only">
              Search candidates and roles
            </label>
            <input
              id="global-search"
              ref={searchRef}
              type="search"
              placeholder="Search candidates, roles…"
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
            />
            <kbd>/</kbd>
          </div>

          <div className="topbar-actions">
            <button type="button" className="icon-button notification-button">
              <Icon name="bell" size={17} title="Notifications" />
              <i aria-hidden="true" />
            </button>
            <button type="button" className="icon-button">
              <Icon name="help" size={17} title="Help" />
            </button>
            <span className="topbar-divider" aria-hidden="true" />
            <UserMenu />
          </div>
        </header>

        <main className="page-content" id="main">
          {children}

          <footer className="app-footer">
            <span>
              Hirewise
              <span className="footer-separator">·</span>
              AI-assisted, human-decided
              <span className="footer-separator">·</span>
              <ApiStatus />
            </span>
            <div>
              <button type="button">Privacy</button>
              <button type="button">How scoring works</button>
              <button type="button">Report a problem</button>
            </div>
          </footer>
        </main>
      </div>
    </div>
  );
}

/** The heading row every page opens with. */
export function PageHeader({
  eyebrow,
  title,
  highlight,
  subtitle,
  action,
}: {
  eyebrow: string;
  title: string;
  highlight?: string;
  subtitle: string;
  action?: ReactNode;
}) {
  return (
    <div className="welcome-row">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>
          {title} {highlight ? <span>{highlight}</span> : null}
        </h1>
        <p className="muted">{subtitle}</p>
      </div>
      {action}
    </div>
  );
}

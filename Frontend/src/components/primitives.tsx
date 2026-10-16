/**
 * Small building blocks shared across pages.
 *
 * Every component renders the class names already defined in `styles.css`
 * rather than introducing new ones, so the design system stays the single
 * source of visual truth.
 */

import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";
import { initials } from "../lib/format";

/* ------------------------------------------------------------- avatar */

export function Avatar({
  name,
  variant,
}: {
  name: string | null | undefined;
  variant?: "small" | "sidebar" | "profile";
}) {
  const className = ["avatar", variant ? `avatar--${variant}` : ""]
    .filter(Boolean)
    .join(" ");

  // The surrounding row already states the person's name, so the monogram is
  // decorative here.
  return (
    <span className={className} aria-hidden="true">
      {initials(name)}
    </span>
  );
}

/* ------------------------------------------------------------- status */

/**
 * Backend states mapped onto the stylesheet's status variants.
 *
 * Each pill shows a word as well as a colour, so the state never depends on
 * colour alone.
 */
const STATUS_STYLES: Record<string, { variant: string; label: string }> = {
  // candidate pipeline
  received: { variant: "new-applicant", label: "New applicant" },
  processing: { variant: "in-review", label: "Processing" },
  processed: { variant: "shortlisted", label: "Screened" },
  screened: { variant: "shortlisted", label: "Screened" },
  error: { variant: "in-review", label: "Needs attention" },
  // decisions
  invited_to_interview: { variant: "interview", label: "Invited" },
  invite_to_interview: { variant: "interview", label: "Invited" },
  reject: { variant: "draft", label: "Not progressed" },
  // interview sessions
  invited: { variant: "scheduled", label: "Invited" },
  in_progress: { variant: "in-review", label: "In progress" },
  submitted: { variant: "published", label: "Submitted" },
  // job lifecycle
  draft: { variant: "draft", label: "Draft" },
  published: { variant: "published", label: "Published" },
  closed: { variant: "draft", label: "Closed" },
  open: { variant: "published", label: "Open" },
  scheduled: { variant: "scheduled", label: "Scheduled" },
  expired: { variant: "draft", label: "Closed" },
  // transcription / scoring
  pending: { variant: "draft", label: "Pending" },
  partial: { variant: "in-review", label: "Partial" },
  completed: { variant: "published", label: "Complete" },
  failed: { variant: "in-review", label: "Failed" },
};

export function StatusPill({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="muted">--</span>;

  const style = STATUS_STYLES[value] ?? {
    variant: "new-applicant",
    label: value.replace(/_/g, " "),
  };

  return (
    <span className={`status status--${style.variant}`}>{style.label}</span>
  );
}

/* -------------------------------------------------------------- panel */

export function Panel({
  title,
  subtitle,
  action,
  className = "",
  children,
}: {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={`panel ${className}`.trim()}>
      {title ? (
        <div className="section-heading">
          <div>
            <h2>{title}</h2>
            {subtitle ? <p className="muted">{subtitle}</p> : null}
          </div>
          {action}
        </div>
      ) : null}
      {children}
    </section>
  );
}

/* ------------------------------------------------------------- metric */

export function MetricCard({
  icon,
  tone,
  label,
  value,
  delta,
}: {
  icon: IconName;
  tone: "blue" | "violet" | "teal" | "amber";
  label: string;
  value: ReactNode;
  delta?: string;
}) {
  return (
    <article className="metric-card">
      <div className={`metric-icon metric-icon--${tone}`}>
        <Icon name={icon} size={18} />
      </div>
      <p className="metric-label">{label}</p>
      <p className="metric-value">{value}</p>
      {delta ? <p className="metric-delta">{delta}</p> : null}
    </article>
  );
}

/* ----------------------------------------------------------- progress */

export function ProgressBar({
  value,
  max = 100,
  tone = "blue",
  label,
}: {
  value: number;
  max?: number;
  tone?: "blue" | "violet" | "teal" | "amber";
  label: string;
}) {
  const percent = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;

  return (
    <div
      className="progress-track"
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={label}
    >
      <span
        className={`progress-fill progress-fill--${tone}`}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}

/* ------------------------------------------------------------ notices */

export function Notice({
  icon = "sparkles",
  title,
  children,
}: {
  icon?: IconName;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="notice">
      <Icon name={icon} size={17} />
      <div>
        <strong>{title}</strong>
        {children ? <p>{children}</p> : null}
      </div>
    </div>
  );
}

export function HelperText({ children }: { children: ReactNode }) {
  return (
    <p className="helper-text">
      <Icon name="info" size={13} />
      <span>{children}</span>
    </p>
  );
}

/* -------------------------------------------------- async UI states */

/**
 * `aria-live` matters here: these regions replace content after a fetch, and
 * a screen reader would otherwise get no word that anything changed.
 */
export function Loading({ what }: { what: string }) {
  return (
    <p className="muted" role="status" aria-live="polite">
      Loading {what}…
    </p>
  );
}

export function ErrorState({
  error,
  onRetry,
}: {
  error: Error;
  onRetry?: () => void;
}) {
  return (
    <div className="notice" role="alert">
      <Icon name="alert" size={17} />
      <div>
        <strong>Something went wrong</strong>
        <p>{error.message}</p>
        {onRetry ? (
          <button type="button" className="text-button" onClick={onRetry}>
            Try again <Icon name="arrow-right" size={12} />
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div style={{ padding: "18px 0" }}>
      <strong style={{ fontSize: 12, color: "#2a3653" }}>{title}</strong>
      {children ? <p className="muted">{children}</p> : null}
    </div>
  );
}

/* -------------------------------------------------------------- modal */

export function Modal({
  title,
  onClose,
  children,
  footer,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onKeyDown={(event) => {
          if (event.key === "Escape") onClose();
        }}
      >
        <div className="modal-heading">
          <h2>{title}</h2>
          <button
            type="button"
            className="icon-button"
            onClick={onClose}
          >
            <Icon name="close" size={16} title="Close dialog" />
          </button>
        </div>
        {children}
        {footer ? <div className="modal-actions">{footer}</div> : null}
      </div>
    </div>
  );
}

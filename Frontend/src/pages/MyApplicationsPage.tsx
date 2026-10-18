/**
 * The signed-in candidate's own tracker: every role they applied to, how far
 * each application has reached, and what is left.
 *
 * The stages are derived server-side (see app/services/application_journey.py)
 * from the real pipeline state, so this page only renders what it is told —
 * it never second-guesses where an application is.
 */

import { api } from "../api/client";
import { useApi } from "../hooks/useApi";
import { Icon, type IconName } from "../components/Icon";
import { formatDate } from "../lib/format";
import {
  EmptyState,
  ErrorState,
  Loading,
  Panel,
} from "../components/primitives";
import type { JourneyStep, JourneyStepState, MyApplication } from "../types";

const STEP_ICON: Record<JourneyStepState, IconName> = {
  done: "check",
  current: "play",
  pending: "clock",
  skipped: "close",
};

export function MyApplicationsPage({
  onBrowseRoles,
}: {
  onBrowseRoles: () => void;
}) {
  const mine = useApi(() => api.myApplications(), []);

  const applications = mine.data?.applications ?? [];

  return (
    <div className="my-applications">
      <section className="candidate-hero">
        <p className="eyebrow">YOUR APPLICATIONS</p>
        <h2>
          Track every role you've <span>applied to</span>
        </h2>
        <p>
          Here's where each of your applications stands and what happens next.
          We update this as your application moves through the process.
        </p>
      </section>

      {mine.error ? (
        <ErrorState error={mine.error} onRetry={mine.reload} />
      ) : mine.loading ? (
        <Panel>
          <Loading what="your applications" />
        </Panel>
      ) : applications.length === 0 ? (
        <Panel>
          <EmptyState title="You haven't applied to anything yet">
            Browse the open roles and apply with your resume — your
            applications will show up here so you can follow their progress.
            <div style={{ marginTop: 14 }}>
              <button
                type="button"
                className="button button--primary"
                onClick={onBrowseRoles}
              >
                Browse open roles <Icon name="arrow-right" size={12} />
              </button>
            </div>
          </EmptyState>
        </Panel>
      ) : (
        <>
          <div className="section-heading">
            <div>
              <h2>
                {applications.length}{" "}
                {applications.length === 1 ? "application" : "applications"}
              </h2>
              <p className="muted">Most recent first</p>
            </div>
            <button
              type="button"
              className="button button--secondary"
              onClick={onBrowseRoles}
            >
              Browse more roles <Icon name="arrow-right" size={12} />
            </button>
          </div>

          <div className="application-list">
            {applications.map((application) => (
              <ApplicationCard key={application.id} application={application} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function ApplicationCard({ application }: { application: MyApplication }) {
  const { current_step, completed_steps, total_steps, steps } = application;
  const pct = total_steps
    ? Math.round((completed_steps / total_steps) * 100)
    : 0;

  const inviteReady =
    application.interview_invite_url &&
    current_step.key === "interview" &&
    application.interview_status !== "submitted";

  return (
    <article className="application-card">
      <header className="application-card-head">
        <span className="job-mark">
          <Icon name="briefcase" size={18} />
        </span>
        <div className="application-card-title">
          <h3>{application.job_title ?? "This role is no longer listed"}</h3>
          <p className="muted">
            {application.applied_at
              ? `Applied ${formatDate(application.applied_at)}`
              : "Application received"}
          </p>
        </div>
        <span className={`stage-badge stage-badge--${current_step.state}`}>
          {current_step.state === "done" ? "Complete" : current_step.title}
        </span>
      </header>

      <div className="application-progress">
        <div className="application-progress-bar">
          <span style={{ width: `${pct}%` }} />
        </div>
        <small className="muted">
          {completed_steps} of {total_steps} steps complete
        </small>
      </div>

      <div className="application-current">
        <strong>What's happening now</strong>
        <p>{current_step.detail}</p>
        {inviteReady ? (
          <a
            className="button button--primary"
            href={application.interview_invite_url!}
          >
            <Icon name="mic" size={13} /> Record your interview
          </a>
        ) : null}
      </div>

      <ol className="journey">
        {steps.map((step) => (
          <JourneyRow key={step.key} step={step} />
        ))}
      </ol>
    </article>
  );
}

function JourneyRow({ step }: { step: JourneyStep }) {
  return (
    <li className={`journey-step journey-step--${step.state}`}>
      <span className="journey-dot">
        <Icon name={STEP_ICON[step.state]} size={12} />
      </span>
      <div className="journey-body">
        <strong>{step.title}</strong>
        <small>{step.detail}</small>
      </div>
    </li>
  );
}

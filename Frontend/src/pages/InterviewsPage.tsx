/**
 * Every interview session and where it has got to.
 *
 * This is the operational view: who has been invited, who is recording, what
 * still needs transcribing or scoring.
 */

import { useState } from "react";
import { api } from "../api/client";
import { useAction, useApi } from "../hooks/useApi";
import { Icon } from "../components/Icon";
import {
  Avatar,
  EmptyState,
  ErrorState,
  Loading,
  Panel,
  ProgressBar,
  StatusPill,
} from "../components/primitives";
import { formatDate } from "../lib/format";
import { PageHeader } from "../components/AppShell";
import type { SessionSummary } from "../types";

export function InterviewsPage({ search }: { search: string }) {
  const [status, setStatus] = useState("");

  const sessions = useApi(
    () => api.listSessions({ status: status || undefined, limit: 200 }),
    [status],
  );

  const rows = (sessions.data?.sessions ?? []).filter((session) =>
    search
      ? `${session.candidate_name ?? ""} ${session.job_title ?? ""}`
          .toLowerCase()
          .includes(search.toLowerCase())
      : true,
  );

  const submitted = rows.filter((session) => session.status === "submitted");
  const transcribed = rows.filter(
    (session) => session.transcription_status === "completed",
  );
  const scored = rows.filter((session) => session.overall_score !== null);

  return (
    <>
      <PageHeader
        eyebrow="INTERVIEWS"
        title="Interview"
        highlight="sessions"
        subtitle="One recorded answer per question, each with its own time limit."
      />

      <div className="toolbar">
        <div className="select-field">
          <label htmlFor="session-status" className="sr-only">
            Filter by status
          </label>
          <select
            id="session-status"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">All statuses</option>
            <option value="invited">Invited</option>
            <option value="in_progress">In progress</option>
            <option value="submitted">Submitted</option>
          </select>
        </div>
      </div>

      <div className="interview-layout">
        <Panel
          title="Sessions"
          subtitle={
            sessions.loading
              ? "Loading…"
              : `${rows.length} ${rows.length === 1 ? "session" : "sessions"}`
          }
        >
          {sessions.error ? (
            <ErrorState error={sessions.error} onRetry={sessions.reload} />
          ) : sessions.loading ? (
            <Loading what="sessions" />
          ) : rows.length === 0 ? (
            <EmptyState title="No interview sessions">
              Invite a screened candidate from their profile to create one.
            </EmptyState>
          ) : (
            rows.map((session) => (
              <SessionRow
                key={session.id}
                session={session}
                onChanged={sessions.reload}
              />
            ))
          )}
        </Panel>

        <Panel title="Pipeline health">
          <div className="feedback-stat">
            <span>Submitted</span>
            <strong>{submitted.length}</strong>
          </div>
          <ProgressBar
            value={submitted.length}
            max={Math.max(1, rows.length)}
            tone="blue"
            label={`${submitted.length} of ${rows.length} sessions submitted`}
          />

          <div className="feedback-stat">
            <span>Transcribed</span>
            <strong>{transcribed.length}</strong>
          </div>
          <ProgressBar
            value={transcribed.length}
            max={Math.max(1, submitted.length)}
            tone="violet"
            label={`${transcribed.length} of ${submitted.length} submitted sessions transcribed`}
          />

          <div className="feedback-stat">
            <span>Scored</span>
            <strong>{scored.length}</strong>
          </div>
          <ProgressBar
            value={scored.length}
            max={Math.max(1, transcribed.length)}
            tone="teal"
            label={`${scored.length} of ${transcribed.length} transcribed sessions scored`}
          />

          <p className="helper-text">
            <Icon name="info" size={13} />
            <span>
              Each stage depends on the one above it: an interview must be
              submitted before it can be transcribed, and transcribed before it
              can be scored.
            </span>
          </p>
        </Panel>
      </div>
    </>
  );
}

function SessionRow({
  session,
  onChanged,
}: {
  session: SessionSummary;
  onChanged: () => void;
}) {
  const transcribe = useAction(api.transcribe);
  const score = useAction(api.score);

  const created = session.created_at ? new Date(session.created_at) : null;

  const needsTranscript =
    session.status === "submitted" && session.transcription_status !== "completed";

  const needsScore =
    session.transcription_status === "completed" && !session.scoring_status;

  return (
    <div className="interview-row">
      <div className="date-tile">
        <small>
          {created
            ? created.toLocaleDateString(undefined, { month: "short" }).toUpperCase()
            : "--"}
        </small>
        <strong>{created ? created.getDate() : "--"}</strong>
      </div>

      <div className="interview-person">
        <Avatar name={session.candidate_name} variant="small" />
        <div>
          <strong>{session.candidate_name ?? "Unnamed candidate"}</strong>
          <p className="muted">{session.job_title ?? "Unknown role"}</p>
          <small>
            {session.answered_count} of {session.total_questions} answered ·{" "}
            {session.submitted_at
              ? `submitted ${formatDate(session.submitted_at)}`
              : "not submitted"}
          </small>
        </div>
      </div>

      <div style={{ display: "grid", gap: 6, justifyItems: "end" }}>
        <StatusPill value={session.status} />
        {session.overall_score !== null ? (
          <span className="review-score">
            {session.overall_score.toFixed(1)} / 5
          </span>
        ) : null}
        {session.needs_human_review ? (
          <span className="status status--in-review">Flagged</span>
        ) : null}

        {needsTranscript ? (
          <button
            type="button"
            className="text-button"
            disabled={transcribe.pending}
            onClick={async () => {
              const done = await transcribe.run(session.id);
              if (done) onChanged();
            }}
          >
            {transcribe.pending ? "Transcribing…" : "Transcribe"}
          </button>
        ) : needsScore ? (
          <button
            type="button"
            className="text-button"
            disabled={score.pending}
            onClick={async () => {
              const done = await score.run(session.id);
              if (done) onChanged();
            }}
          >
            {score.pending ? "Scoring…" : "Score"}
          </button>
        ) : null}

        {transcribe.error || score.error ? (
          <span className="table-subtext" role="alert">
            {(transcribe.error ?? score.error)!.message}
          </span>
        ) : null}
      </div>
    </div>
  );
}

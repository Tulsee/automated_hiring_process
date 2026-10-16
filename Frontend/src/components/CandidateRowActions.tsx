/**
 * The action a candidate is actually waiting on, offered inline in the list.
 *
 * A candidate moves through the pipeline in a fixed order, and at any moment
 * exactly one step is available:
 *
 *   scored but undecided  -> run the screening decision
 *   decided, no session   -> create their interview invite
 *   session exists        -> copy the invite link
 *   not progressed        -> nothing to do
 *
 * So the column shows one button rather than a menu of mostly-disabled ones.
 * Each button names the candidate in its accessible label, because twenty rows
 * of "Screen" are indistinguishable to a screen reader.
 */

import { useState } from "react";
import { api } from "../api/client";
import { useAction } from "../hooks/useApi";
import { Icon } from "./Icon";
import { isEligibleForInterview } from "../lib/pipeline";
import type { CandidateSummary } from "../types";

type Feedback = { tone: "ok" | "bad"; text: string } | null;

export function CandidateRowActions({
  candidate,
  onChanged,
}: {
  candidate: CandidateSummary;
  onChanged: () => void;
}) {
  const [feedback, setFeedback] = useState<Feedback>(null);

  const screen = useAction(api.screenCandidate);
  const invite = useAction(api.createSession);
  const link = useAction(api.getCandidate);

  const name = candidate.name ?? "this candidate";
  const busy = screen.pending || invite.pending || link.pending;

  /** Copy to the clipboard, falling back to showing the link. */
  async function copy(url: string) {
    try {
      await navigator.clipboard.writeText(url);
      setFeedback({ tone: "ok", text: "Invite link copied" });
    } catch {
      // Clipboard access needs a secure context, which plain HTTP is not.
      setFeedback({ tone: "ok", text: url });
    }
  }

  const actions = [];

  if (!candidate.decision) {
    actions.push(
      <button
        key="screen"
        type="button"
        className="text-button"
        disabled={busy}
        aria-label={`Run screening decision for ${name}`}
        onClick={async () => {
          setFeedback(null);

          const result = await screen.run(candidate.id);

          if (result) {
            setFeedback({
              tone: "ok",
              text: `Decision: ${result.decision.replace(/_/g, " ")}`,
            });
            onChanged();
          }
        }}
      >
        <Icon name="sparkles" size={12} />
        {screen.pending ? "Screening…" : "Screen"}
      </button>,
    );
  } else if (
    !candidate.interview_session_id &&
    isEligibleForInterview(candidate.decision)
  ) {
    actions.push(
      <button
        key="invite"
        type="button"
        className="text-button"
        disabled={busy}
        aria-label={`Create an interview invite for ${name}`}
        onClick={async () => {
          setFeedback(null);

          const created = await invite.run(candidate.id);

          if (created) {
            await copy(created.invite_url);
            onChanged();
          }
        }}
      >
        <Icon name="calendar" size={12} />
        {invite.pending ? "Inviting…" : "Invite"}
      </button>,
    );
  } else if (candidate.interview_session_id) {
    actions.push(
      <button
        key="link"
        type="button"
        className="text-button"
        disabled={busy}
        aria-label={`Copy the interview invite link for ${name}`}
        onClick={async () => {
          setFeedback(null);

          // The list row carries the session id but not the link, so the
          // candidate is read to get it.
          const detail = await link.run(candidate.id);

          if (!detail) return;

          if (detail.interview.invite_url) {
            await copy(detail.interview.invite_url);
          } else {
            setFeedback({
              tone: "bad",
              text: "No invite link stored for this session",
            });
          }
        }}
      >
        <Icon name="external" size={12} />
        {link.pending ? "Fetching…" : "Copy link"}
      </button>,
    );
  }

  const error = screen.error ?? invite.error ?? link.error;

  if (actions.length === 0 && !error && !feedback) {
    return <span className="muted">--</span>;
  }

  return (
    <div className="row-actions">
      {actions}

      {error ? (
        <span className="row-actions-note is-bad" role="alert">
          {error.message}
        </span>
      ) : feedback ? (
        <span
          className={`row-actions-note${feedback.tone === "bad" ? " is-bad" : ""}`}
          role="status"
        >
          {feedback.text}
        </span>
      ) : null}
    </div>
  );
}

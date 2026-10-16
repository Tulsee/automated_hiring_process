/**
 * The review screen: one interview, its AI scorecard, and the evidence.
 *
 * This is the page where a person makes the call, so it is built to make the
 * AI's reasoning inspectable rather than persuasive:
 *
 *   - the flagged-for-review banner comes before the score,
 *   - every score sits next to the candidate's own words,
 *   - the weighting and the rubric are both openable,
 *   - and the transcript and recording are one click away.
 *
 * The Approve / Override buttons are present but inert until the backend
 * exposes the graph's interrupt-and-resume (Module 17); they say so rather
 * than pretending to work.
 */

import { useState } from "react";
import { api } from "../api/client";
import { useAction, useApi } from "../hooks/useApi";
import { Icon } from "../components/Icon";
import {
  AiScoreBlock,
  CompetencyRow,
  EvidenceList,
  FlagList,
  ReviewBanner,
  RubricDisclosure,
  WeightingDisclosure,
} from "../components/AiRecommendation";
import { flagLabel } from "../lib/flags";
import {
  Avatar,
  EmptyState,
  ErrorState,
  Loading,
  Notice,
  Panel,
  StatusPill,
} from "../components/primitives";
import { formatSeconds, humanise } from "../lib/format";
import { PageHeader } from "../components/AppShell";
import type { SessionSummary } from "../types";

export function ReviewPage({ search }: { search: string }) {
  const sessions = useApi(() => api.listSessions({ limit: 200 }), []);

  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Only submitted interviews are reviewable; flagged ones come first because
  // they are the ones a person actually has to look at.
  const reviewable = (sessions.data?.sessions ?? [])
    .filter((session) => session.status === "submitted")
    .filter((session) =>
      search
        ? `${session.candidate_name ?? ""} ${session.job_title ?? ""}`
            .toLowerCase()
            .includes(search.toLowerCase())
        : true,
    )
    .sort((a, b) => {
      const flagged = Number(b.needs_human_review) - Number(a.needs_human_review);
      if (flagged !== 0) return flagged;

      return (b.overall_score ?? -1) - (a.overall_score ?? -1);
    });

  // Derived rather than synced through an effect: the selection defaults to
  // the top of the queue until the reviewer picks someone else.
  const selected =
    reviewable.find((session) => session.id === selectedId) ?? reviewable[0];

  return (
    <>
      <PageHeader
        eyebrow="REVIEW QUEUE"
        title="Interview"
        highlight="review"
        subtitle="The model scores and shows its evidence. The decision is yours."
      />

      {sessions.error ? (
        <ErrorState error={sessions.error} onRetry={sessions.reload} />
      ) : sessions.loading ? (
        <Panel>
          <Loading what="the review queue" />
        </Panel>
      ) : reviewable.length === 0 ? (
        <Panel>
          <EmptyState title="Nothing to review yet">
            Interviews appear here once a candidate has submitted every answer.
          </EmptyState>
        </Panel>
      ) : (
        <div className="review-layout">
          <Panel className="review-list">
            <h3>Submitted interviews</h3>
            <p className="muted">
              {reviewable.filter((s) => s.needs_human_review).length} flagged for
              a closer look
            </p>

            {reviewable.map((session) => (
              <QueueRow
                key={session.id}
                session={session}
                selected={session.id === selected?.id}
                onSelect={() => setSelectedId(session.id)}
              />
            ))}
          </Panel>

          {selected ? (
            // Keyed by session: a different candidate gets a fresh component,
            // which resets the decision without an effect.
            <ReviewDetail
              key={selected.id}
              sessionId={selected.id}
              session={selected}
              onChanged={sessions.reload}
            />
          ) : null}
        </div>
      )}
    </>
  );
}

function QueueRow({
  session,
  selected,
  onSelect,
}: {
  session: SessionSummary;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={`review-candidate ${selected ? "is-selected" : ""}`.trim()}
      aria-current={selected ? "true" : undefined}
      onClick={onSelect}
    >
      <Avatar name={session.candidate_name} variant="small" />
      <span>
        <strong>{session.candidate_name ?? "Unnamed candidate"}</strong>
        <small>
          {session.job_title ?? "Unknown role"}
          {session.needs_human_review ? " · flagged" : ""}
        </small>
      </span>
      <span className="review-score">
        {session.overall_score !== null
          ? session.overall_score.toFixed(1)
          : session.scoring_status
            ? "--"
            : "new"}
      </span>
    </button>
  );
}

function ReviewDetail({
  sessionId,
  session,
  onChanged,
}: {
  sessionId: string;
  session?: SessionSummary;
  onChanged: () => void;
}) {
  const scorecard = useApi(
    () => api.getScorecard(sessionId).catch(() => null),
    [sessionId],
  );
  const transcripts = useApi(() => api.getTranscripts(sessionId), [sessionId]);

  const runScore = useAction(api.score);
  const runTranscribe = useAction(api.transcribe);

  const [decision, setDecision] = useState<string | null>(null);

  const result = scorecard.data;
  const card = result?.scorecard;

  const needsTranscription =
    transcripts.data && transcripts.data.transcription_status !== "completed";

  return (
    <Panel className="review-detail">
      <div className="review-profile">
        <Avatar name={session?.candidate_name} />
        <div>
          <h2>{session?.candidate_name ?? "Candidate"}</h2>
          <p className="muted">
            {session?.job_title ?? "Unknown role"} ·{" "}
            {session?.answered_count ?? 0} of {session?.total_questions ?? 0}{" "}
            answered
          </p>
        </div>
        <StatusPill value={session?.status} />
      </div>

      {/* Pipeline prerequisites come first: you cannot review what has not
          been transcribed and scored. */}
      {needsTranscription ? (
        <>
          <Notice icon="mic" title="Not transcribed yet">
            The recordings need turning into text before they can be scored.
            This runs speech-to-text on the server and can take a minute per
            answer.
          </Notice>
          <button
            type="button"
            className="button button--primary"
            disabled={runTranscribe.pending}
            onClick={async () => {
              const done = await runTranscribe.run(sessionId);
              if (done) {
                transcripts.reload();
                onChanged();
              }
            }}
          >
            {runTranscribe.pending ? "Transcribing…" : "Transcribe answers"}
          </button>
          {runTranscribe.error ? (
            <p className="table-note" role="alert">
              {runTranscribe.error.message}
            </p>
          ) : null}
        </>
      ) : !card ? (
        <>
          <Notice icon="sparkles" title="Not scored yet">
            Transcripts are ready. Scoring reads each answer against the role's
            rubric and returns a score with the quote it was based on.
          </Notice>
          <button
            type="button"
            className="button button--primary"
            disabled={runScore.pending}
            onClick={async () => {
              const done = await runScore.run(sessionId);
              if (done) {
                scorecard.reload();
                onChanged();
              }
            }}
          >
            {runScore.pending ? "Scoring…" : "Score this interview"}
          </button>
          {runScore.error ? (
            <p className="table-note" role="alert">
              {runScore.error.message}
            </p>
          ) : null}
        </>
      ) : (
        <>
          <ReviewBanner scorecard={card} />

          <AiScoreBlock
            scorecard={card}
            model={result?.answer_scores.find((s) => s.model)?.model}
          />

          <h3>By competency</h3>
          {card.competency_scores.map((competency) => (
            <CompetencyRow
              key={competency.competency}
              competency={competency}
              scale={card.scale}
            />
          ))}

          <WeightingDisclosure scorecard={card} />
          <RubricDisclosure scorecard={card} />

          <h3 style={{ marginTop: 20 }}>Evidence</h3>
          <p className="muted" style={{ marginBottom: 12 }}>
            Each score below shows the candidate's own words it was based on,
            and whether that quote was found in the transcript.
          </p>
          <EvidenceList
            scores={result!.answer_scores}
            scale={card.scale}
          />

          <TranscriptSection sessionId={sessionId} />

          <h3 style={{ marginTop: 22 }}>Your decision</h3>
          {decision ? (
            <p className="inline-confirm">
              <Icon name="check" size={14} />
              Recorded locally: {decision}. Nothing was sent — the decision step
              needs the pipeline's human-in-the-loop hook.
            </p>
          ) : (
            <>
              <p className="muted">
                These buttons will resume the paused hiring pipeline once that
                step exists. For now they record your choice in this screen only.
              </p>
              <div className="review-actions">
                <button
                  type="button"
                  className="button button--primary"
                  onClick={() => setDecision("advance")}
                >
                  <Icon name="check" size={14} /> Advance candidate
                </button>
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => setDecision("override to reject")}
                >
                  Override to reject
                </button>
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => setDecision("second opinion requested")}
                >
                  Ask for a second opinion
                </button>
              </div>
            </>
          )}

          {card.flags.length > 0 ? (
            <>
              <h3 style={{ marginTop: 18 }}>Everything flagged</h3>
              <FlagList flags={card.flags} />
            </>
          ) : null}

          <button
            type="button"
            className="text-button"
            disabled={runScore.pending}
            onClick={async () => {
              const done = await runScore.run(sessionId);
              if (done) scorecard.reload();
            }}
          >
            {runScore.pending ? "Re-scoring…" : "Re-run scoring"}{" "}
            <Icon name="arrow-right" size={12} />
          </button>
        </>
      )}
    </Panel>
  );
}

/** Transcripts and the recording behind each answer. */
function TranscriptSection({ sessionId }: { sessionId: string }) {
  const transcripts = useApi(() => api.getTranscripts(sessionId), [sessionId]);
  const [openId, setOpenId] = useState<string | null>(null);

  if (transcripts.loading) return <Loading what="transcripts" />;

  const items = transcripts.data?.transcripts ?? [];

  if (items.length === 0) return null;

  return (
    <>
      <h3 style={{ marginTop: 22 }}>Transcripts and recordings</h3>
      <p className="muted" style={{ marginBottom: 6 }}>
        Speech-to-text drops and occasionally invents words. The audio is kept
        so you can check anything that reads oddly.
      </p>

      {items.map((item) => {
        const open = openId === item.question_id;

        return (
          <div key={item.question_id} style={{ borderBottom: "1px solid #edf0f5" }}>
            <button
              type="button"
              className="accordion-button"
              aria-expanded={open}
              onClick={() => setOpenId(open ? null : item.question_id)}
            >
              <span>
                {humanise(item.competency)}
                <span className="table-subtext">
                  {item.question_text ?? item.question_id} · {item.word_count}{" "}
                  words · {formatSeconds(item.duration_seconds)}
                </span>
              </span>
              <Icon name={open ? "chevron-up" : "chevron-down"} size={14} />
            </button>

            {open ? (
              <div style={{ paddingBottom: 16 }}>
                {item.flags.length > 0 ? (
                  <p
                    className="helper-text"
                    style={{ color: "#a9751c", marginTop: 0 }}
                  >
                    <Icon name="alert" size={13} />
                    <span>{item.flags.map(flagLabel).join(" ")}</span>
                  </p>
                ) : null}

                <p style={{ fontSize: 11, lineHeight: 1.75, color: "#56627d" }}>
                  {item.transcript || "No speech was detected in this answer."}
                </p>

                <video
                  controls
                  preload="none"
                  src={api.answerVideoUrl(sessionId, item.question_id)}
                  style={{
                    width: "100%",
                    maxWidth: 420,
                    borderRadius: 9,
                    background: "#000",
                  }}
                >
                  <track kind="captions" label="No captions available" />
                </video>

                <p className="table-note">
                  Transcribed by {item.model ?? "unknown model"}
                  {item.language ? ` · detected language: ${item.language}` : ""}
                </p>
              </div>
            ) : null}
          </div>
        );
      })}
    </>
  );
}

/**
 * Recruiter overview: pipeline health, who needs attention, what to do next.
 *
 * Everything here is derived from two list endpoints rather than a bespoke
 * stats API, so the numbers always agree with the pages they link to.
 */

import { api } from "../api/client";
import { useApi } from "../hooks/useApi";
import { Icon } from "../components/Icon";
import { ScoreCell } from "../components/AiRecommendation";
import {
  Avatar,
  ErrorState,
  HelperText,
  Loading,
  MetricCard,
  Panel,
  ProgressBar,
  StatusPill,
} from "../components/primitives";
import { formatDate } from "../lib/format";
import { PageHeader } from "../components/AppShell";
import type { ViewId } from "../lib/nav";

export function DashboardPage({
  onNavigate,
  onOpenCandidate,
  onCreateJob,
}: {
  onNavigate: (view: ViewId) => void;
  onOpenCandidate: (candidateId: string) => void;
  onCreateJob: () => void;
}) {
  const candidates = useApi(() => api.listCandidates({ limit: 200 }), []);
  const sessions = useApi(() => api.listSessions({ limit: 200 }), []);
  const jobs = useApi(() => api.listJobs(), []);

  if (candidates.error) {
    return <ErrorState error={candidates.error} onRetry={candidates.reload} />;
  }

  const rows = candidates.data?.candidates ?? [];
  const allSessions = sessions.data?.sessions ?? [];

  const scored = rows.filter((row) => row.screening_score !== null);

  const averageScore =
    scored.length > 0
      ? scored.reduce((total, row) => total + (row.screening_score ?? 0), 0) /
        scored.length
      : null;

  // The four pipeline stages, counted from the candidate and session lists.
  const stages = [
    {
      label: "Applied",
      count: rows.length,
      tone: "blue" as const,
      hint: "Resume received",
    },
    {
      label: "Screened",
      count: scored.length,
      tone: "violet" as const,
      hint: "AI screening done",
    },
    {
      label: "Interviewing",
      count: allSessions.filter((s) => s.status !== "submitted").length,
      tone: "amber" as const,
      hint: "Invited or recording",
    },
    {
      label: "Ready to review",
      count: allSessions.filter((s) => s.status === "submitted").length,
      tone: "teal" as const,
      hint: "Interview complete",
    },
  ];

  const pipelineMax = Math.max(1, ...stages.map((stage) => stage.count));

  const needsReview = allSessions.filter((s) => s.needs_human_review);
  const awaitingScore = allSessions.filter(
    (s) => s.transcription_status === "completed" && !s.scoring_status,
  );
  const awaitingTranscript = allSessions.filter(
    (s) => s.status === "submitted" && s.transcription_status !== "completed",
  );

  const recent = [...rows]
    .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))
    .slice(0, 6);

  return (
    <>
      <PageHeader
        eyebrow="OVERVIEW"
        title="Good to see you,"
        highlight="Tulsee"
        subtitle="Here is where your pipeline stands today. AI handles the sorting; you make the calls."
        action={
          <button type="button" className="button button--primary" onClick={onCreateJob}>
            <Icon name="plus" size={14} /> New role
          </button>
        }
      />

      <div className="metrics-grid">
        <MetricCard
          icon="users"
          tone="blue"
          label="Candidates"
          value={candidates.loading ? "--" : rows.length}
          delta={`${jobs.data?.length ?? 0} open roles`}
        />
        <MetricCard
          icon="sparkles"
          tone="violet"
          label="Average screening score"
          value={averageScore !== null ? averageScore.toFixed(1) : "--"}
          delta={`${scored.length} scored`}
        />
        <MetricCard
          icon="calendar"
          tone="teal"
          label="Interviews submitted"
          value={allSessions.filter((s) => s.status === "submitted").length}
          delta={`${allSessions.length} sessions total`}
        />
        <MetricCard
          icon="clipboard"
          tone="amber"
          label="Flagged for review"
          value={needsReview.length}
          delta={needsReview.length ? "Needs a human look" : "Nothing flagged"}
        />
      </div>

      <div className="dashboard-grid">
        <div className="main-column">
          <Panel
            title="Pipeline"
            subtitle="Where every candidate currently sits"
            action={
              <button
                type="button"
                className="text-button"
                onClick={() => onNavigate("candidates")}
              >
                View all <Icon name="chevron-right" size={12} />
              </button>
            }
          >
            <div className="pipeline">
              {stages.map((stage) => (
                <div className="pipeline-stage" key={stage.label}>
                  <div className="pipeline-stage-top">
                    <span>{stage.label}</span>
                    <strong>{stage.count}</strong>
                  </div>
                  <ProgressBar
                    value={stage.count}
                    max={pipelineMax}
                    tone={stage.tone}
                    label={`${stage.label}: ${stage.count} candidates`}
                  />
                  <small>{stage.hint}</small>
                </div>
              ))}
            </div>
            <HelperText>
              Counts come straight from the candidate and interview records, so
              they always match the detail pages.
            </HelperText>
          </Panel>

          <Panel
            title="Recent candidates"
            subtitle="Newest applications first"
            action={
              <button
                type="button"
                className="text-button"
                onClick={() => onNavigate("candidates")}
              >
                All candidates <Icon name="chevron-right" size={12} />
              </button>
            }
          >
            {candidates.loading ? (
              <Loading what="candidates" />
            ) : recent.length === 0 ? (
              <p className="muted">
                No applications yet. Publish a role and share its link.
              </p>
            ) : (
              <div className="table-scroll">
                <table>
                  <caption className="sr-only">
                    Recent candidates with screening score and stage
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Candidate</th>
                      <th scope="col">Screening</th>
                      <th scope="col">Stage</th>
                      <th scope="col">Applied</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recent.map((row) => (
                      <tr key={row.id}>
                        <td>
                          <button
                            type="button"
                            className="candidate-name"
                            onClick={() => onOpenCandidate(row.id)}
                          >
                            <Avatar name={row.name} variant="small" />
                            <span>
                              <strong>{row.name ?? "Unnamed candidate"}</strong>
                              <small>{row.email ?? row.resume_filename ?? "--"}</small>
                            </span>
                          </button>
                        </td>
                        <td>
                          <ScoreCell
                            value={row.screening_score}
                            caption={
                              row.screening_score === null ? "Not screened" : "AI score"
                            }
                          />
                        </td>
                        <td>
                          <StatusPill value={row.decision ?? row.status} />
                        </td>
                        <td>{formatDate(row.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="table-note">
              Scores are AI suggestions based on resume text. Open a candidate to
              see what the score was based on.
            </p>
          </Panel>
        </div>

        <div className="side-column">
          <section className="ai-promo">
            <span className="promo-orb orb-one" aria-hidden="true" />
            <span className="promo-orb orb-two" aria-hidden="true" />
            <span className="promo-icon">
              <Icon name="sparkles" size={18} />
            </span>
            <p className="eyebrow">REVIEW QUEUE</p>
            <h2>
              {needsReview.length > 0
                ? `${needsReview.length} need you`
                : "Queue is clear"}
            </h2>
            <p>
              {needsReview.length > 0
                ? "Some interviews could not be scored reliably. Read the evidence and decide."
                : "Every scored interview had verified evidence. Nothing is waiting on you."}
            </p>
            <button
              type="button"
              className="button button--light"
              onClick={() => onNavigate("review")}
            >
              Open review queue <Icon name="arrow-right" size={12} />
            </button>
          </section>

          <Panel title="What needs doing" className="insights-panel">
            <div className="insight-row">
              <span className="insight-icon insight-icon--blue">
                <Icon name="mic" size={16} />
              </span>
              <div>
                <p className="insight-title">Awaiting transcription</p>
                <strong>{awaitingTranscript.length} interviews</strong>
                <p className="insight-detail muted">
                  Submitted but not yet turned into text.
                </p>
              </div>
            </div>
            <div className="insight-row">
              <span className="insight-icon insight-icon--violet">
                <Icon name="sparkles" size={16} />
              </span>
              <div>
                <p className="insight-title">Ready to score</p>
                <strong>{awaitingScore.length} interviews</strong>
                <p className="insight-detail muted">
                  Transcribed and waiting for rubric scoring.
                </p>
              </div>
            </div>
            <div className="insight-row">
              <span className="insight-icon insight-icon--teal">
                <Icon name="briefcase" size={16} />
              </span>
              <div>
                <p className="insight-title">Open roles</p>
                <strong>{jobs.data?.length ?? 0} published</strong>
                <p className="insight-detail muted">
                  Each with its own questions and rubric.
                </p>
              </div>
            </div>
          </Panel>

          <Panel title="Quick actions" className="quick-panel">
            <button type="button" onClick={onCreateJob}>
              <Icon name="plus" size={15} /> Create a role
              <Icon name="chevron-right" size={13} />
            </button>
            <button type="button" onClick={() => onNavigate("interviews")}>
              <Icon name="calendar" size={15} /> Manage interviews
              <Icon name="chevron-right" size={13} />
            </button>
            <button type="button" onClick={() => onNavigate("portal")}>
              <Icon name="users" size={15} /> See the candidate view
              <Icon name="chevron-right" size={13} />
            </button>
          </Panel>
        </div>
      </div>
    </>
  );
}

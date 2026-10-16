/**
 * The candidate list, and the detail drawer it opens.
 *
 * Filtering is done by the API rather than in the browser, so the counts shown
 * are the real totals and paging stays honest.
 */

import { useState } from "react";
import { api, type CandidateFilters } from "../api/client";
import { useAction, useApi } from "../hooks/useApi";

import { ScoreCell, ScreeningBreakdown, SkillChips } from "../components/AiRecommendation";
import {
  Avatar,
  ErrorState,
  Loading,
  Modal,
  Notice,
  Panel,
  ProgressBar,
  StatusPill,
} from "../components/primitives";
import { formatDate } from "../lib/format";
import { PageHeader } from "../components/AppShell";
import { CandidateDiagnostics } from "../components/CandidateDiagnostics";
import type { CandidateSummary } from "../types";

export function CandidatesPage({
  search,
  jobFilter,
  onJobFilterChange,
  openCandidateId,
  onOpenCandidate,
}: {
  search: string;
  jobFilter: string;
  onJobFilterChange: (jobId: string) => void;
  openCandidateId: string | null;
  onOpenCandidate: (candidateId: string | null) => void;
}) {
  const [decision, setDecision] = useState("");
  const [sort, setSort] = useState<CandidateFilters["sort"]>("score");
  const [offset, setOffset] = useState(0);

  const limit = 25;

  const jobs = useApi(() => api.listJobs(), []);

  const list = useApi(
    () =>
      api.listCandidates({
        job_id: jobFilter || undefined,
        decision: decision || undefined,
        sort,
        limit,
        offset,
      }),
    [jobFilter, decision, sort, offset],
  );

  // Name search is client-side: the API filters by job, decision and score,
  // not by free text.
  const rows = (list.data?.candidates ?? []).filter((row) =>
    search
      ? `${row.name ?? ""} ${row.email ?? ""}`
          .toLowerCase()
          .includes(search.toLowerCase())
      : true,
  );

  const total = list.data?.total ?? 0;

  return (
    <>
      <PageHeader
        eyebrow="PEOPLE"
        title="All"
        highlight="candidates"
        subtitle="Ranked by AI screening score. Open anyone to see what their score was based on."
      />

      <div className="toolbar">
        <div className="select-field">
          <label htmlFor="job-filter" className="sr-only">
            Filter by role
          </label>
          <select
            id="job-filter"
            value={jobFilter}
            onChange={(event) => {
              onJobFilterChange(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">All roles</option>
            {(jobs.data ?? []).map((job) => (
              <option key={job.id} value={job.id}>
                {job.title}
              </option>
            ))}
          </select>
        </div>

        <div className="select-field">
          <label htmlFor="decision-filter" className="sr-only">
            Filter by decision
          </label>
          <select
            id="decision-filter"
            value={decision}
            onChange={(event) => {
              setDecision(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">Any decision</option>
            <option value="invited_to_interview">Invited to interview</option>
            <option value="reject">Not progressed</option>
          </select>
        </div>

        <div className="select-field">
          <label htmlFor="sort-by" className="sr-only">
            Sort by
          </label>
          <select
            id="sort-by"
            value={sort}
            onChange={(event) => {
              setSort(event.target.value as CandidateFilters["sort"]);
              setOffset(0);
            }}
          >
            <option value="score">Highest score</option>
            <option value="recent">Most recent</option>
            <option value="name">Name</option>
          </select>
        </div>
      </div>

      <Panel
        title={list.data?.job_title ? `${list.data.job_title}` : "Candidates"}
        subtitle={
          list.loading ? "Loading…" : `${total} matching ${total === 1 ? "candidate" : "candidates"}`
        }
      >
        {list.error ? (
          <ErrorState error={list.error} onRetry={list.reload} />
        ) : list.loading ? (
          <Loading what="candidates" />
        ) : rows.length === 0 ? (
          <p className="muted">
            {search
              ? `No candidates match "${search}" on this page.`
              : "No candidates match these filters."}
          </p>
        ) : (
          <>
            <div className="table-scroll">
              <table>
                <caption className="sr-only">
                  Candidates with screening score, stage and interview progress
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Candidate</th>
                    <th scope="col">Screening score</th>
                    <th scope="col">Experience</th>
                    <th scope="col">Stage</th>
                    <th scope="col">Interview</th>
                    <th scope="col">Applied</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <CandidateRow
                      key={row.id}
                      row={row}
                      onOpen={() => onOpenCandidate(row.id)}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                marginTop: 14,
              }}
            >
              <button
                type="button"
                className="button button--secondary"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - limit))}
              >
                Previous
              </button>
              <button
                type="button"
                className="button button--secondary"
                disabled={offset + limit >= total}
                onClick={() => setOffset(offset + limit)}
              >
                Next
              </button>
              <span className="muted">
                Showing {total === 0 ? 0 : offset + 1}–
                {Math.min(offset + limit, total)} of {total}
              </span>
            </div>
          </>
        )}
      </Panel>

      {openCandidateId ? (
        <CandidateDetailModal
          candidateId={openCandidateId}
          onClose={() => onOpenCandidate(null)}
        />
      ) : null}
    </>
  );
}

function CandidateRow({
  row,
  onOpen,
}: {
  row: CandidateSummary;
  onOpen: () => void;
}) {
  return (
    <tr>
      <td>
        <button type="button" className="candidate-name" onClick={onOpen}>
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
          caption={row.screening_score === null ? "Not screened" : "AI score"}
        />
      </td>
      <td>
        {row.years_of_experience !== null ? `${row.years_of_experience}y` : "--"}
        <span className="table-subtext">{row.skills_count} skills</span>
      </td>
      <td>
        <StatusPill value={row.decision ?? row.status} />
      </td>
      <td>
        {row.interview_session_id ? (
          <StatusPill value="invited" />
        ) : (
          <span className="muted">--</span>
        )}
      </td>
      <td>{formatDate(row.created_at)}</td>
    </tr>
  );
}

function CandidateDetailModal({
  candidateId,
  onClose,
}: {
  candidateId: string;
  onClose: () => void;
}) {
  const detail = useApi(() => api.getCandidate(candidateId), [candidateId]);
  const invite = useAction(api.createSession);
  const screen = useAction(api.screenCandidate);

  const candidate = detail.data;

  return (
    <Modal title="Candidate detail" onClose={onClose}>
      {detail.error ? (
        <ErrorState error={detail.error} onRetry={detail.reload} />
      ) : !candidate ? (
        <Loading what="candidate" />
      ) : (
        <>
          <div className="profile-modal-head">
            <Avatar name={candidate.name} />
            <div>
              <h2>{candidate.name ?? "Unnamed candidate"}</h2>
              <p className="muted">
                {candidate.email ?? "No email extracted"} ·{" "}
                {candidate.job_title ?? "Unknown role"}
              </p>
              <StatusPill value={candidate.decision ?? candidate.status} />
            </div>
          </div>

          {candidate.status === "error" ? (
            <Notice icon="alert" title="Processing failed">
              This resume could not be parsed, so there is no score. Re-upload it
              or check the server logs.
            </Notice>
          ) : null}

          <ScreeningBreakdown
            score={candidate.screening.screening_score}
            semantic={candidate.screening.semantic_similarity}
            skill={candidate.screening.skill_score}
            experience={candidate.screening.experience_score}
            matched={candidate.screening.matched_skills}
            missing={candidate.screening.missing_skills}
            rationale={candidate.screening.rationale}
          />

          {/* Uploading a resume scores a candidate but does not decide
              anything. This is the step that sets the decision, emails them and
              creates their interview session, so without it a scored candidate
              never progresses. */}
          {!candidate.decision ? (
            <>
              <h3>Screening decision</h3>
              <Notice icon="sparkles" title="Not decided yet">
                This candidate has been scored but no decision has been made.
                Running it sets the decision, emails the candidate, and creates
                their interview session if they pass. It calls the model and
                sends mail, so it takes a while.
              </Notice>
              <button
                type="button"
                className="button button--primary button--wide"
                disabled={screen.pending}
                onClick={async () => {
                  const result = await screen.run(candidateId);
                  if (result) detail.reload();
                }}
              >
                {screen.pending ? "Screening…" : "Run screening decision"}
              </button>
              {screen.error ? (
                <p className="table-note" role="alert">
                  {screen.error.message}
                </p>
              ) : null}
            </>
          ) : candidate.decision_message ? (
            <>
              <h3>Screening decision</h3>
              <p className="muted">{candidate.decision_message}</p>
            </>
          ) : null}

          <h3>Interview</h3>
          {candidate.interview.session_id ? (
            <>
              <div className="pipeline-stage-top">
                <span>
                  Answered {candidate.interview.answered_count} of{" "}
                  {candidate.interview.total_questions}
                </span>
                <strong>
                  <StatusPill value={candidate.interview.status} />
                </strong>
              </div>
              <ProgressBar
                value={candidate.interview.answered_count}
                max={Math.max(1, candidate.interview.total_questions)}
                tone="violet"
                label={`Interview progress: ${candidate.interview.answered_count} of ${candidate.interview.total_questions} answered`}
              />
              {candidate.interview.invite_url ? (
                <p className="table-note">
                  Invite link:{" "}
                  <a href={candidate.interview.invite_url}>
                    {candidate.interview.invite_url}
                  </a>
                </p>
              ) : null}
            </>
          ) : (
            <>
              <p className="muted">
                No interview session yet.
                {candidate.decision
                  ? " This candidate was invited before sessions were created automatically."
                  : " Screen the candidate first."}
              </p>
              <button
                type="button"
                className="button button--primary button--wide"
                disabled={invite.pending}
                onClick={async () => {
                  const created = await invite.run(candidateId);
                  if (created) detail.reload();
                }}
              >
                {invite.pending ? "Creating…" : "Create interview invite"}
              </button>
              {invite.error ? (
                <p className="table-note" role="alert">
                  {invite.error.message}
                </p>
              ) : null}
            </>
          )}

          {candidate.skills.length > 0 ? (
            <>
              <h3>Skills from the resume</h3>
              <SkillChips skills={candidate.skills} tone="neutral" />
            </>
          ) : null}

          {candidate.education.length > 0 ? (
            <>
              <h3>Education</h3>
              {candidate.education.map((entry, index) => (
                <p className="muted" key={index}>
                  {entry.degree ?? "Unknown"} ·{" "}
                  {entry.institution ?? "Unknown institution"}{" "}
                  {entry.year ? `(${entry.year})` : ""}
                </p>
              ))}
            </>
          ) : null}

          <CandidateDiagnostics candidateId={candidateId} />
        </>
      )}
    </Modal>
  );
}

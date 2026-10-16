/**
 * The applicant's side: browse roles, apply with a resume.
 *
 * Applicants are told plainly that AI reads their resume, what it looks at,
 * and that a person decides. That disclosure is the point of the page, not
 * decoration — it is the only screen where the person being scored can see
 * how the scoring works.
 */

import { useRef, useState } from "react";
import { api } from "../api/client";
import { useAction, useApi } from "../hooks/useApi";
import { Icon } from "../components/Icon";
import { SkillChips } from "../components/AiRecommendation";
import { formatDate } from "../lib/format";
import {
  EmptyState,
  ErrorState,
  Loading,
  Modal,
  Notice,
  Panel,
} from "../components/primitives";
import type { Job } from "../types";

export function CandidatePortalPage({ search }: { search: string }) {
  // Only roles accepting applications: a draft, one not yet published, or
  // one past its deadline must not appear here at all.
  const jobs = useApi(() => api.listJobs({ openOnly: true }), []);
  const [query, setQuery] = useState("");
  const [applyTo, setApplyTo] = useState<Job | null>(null);

  const term = (query || search).toLowerCase();

  const visible = (jobs.data ?? []).filter((job) =>
    term
      ? `${job.title} ${job.description} ${job.required_skills.join(" ")}`
          .toLowerCase()
          .includes(term)
      : true,
  );

  return (
    <div className="candidate-portal">
      <section className="candidate-hero">
        <p className="eyebrow">OPEN ROLES</p>
        <h2>
          Find your next role, <span>fairly reviewed</span>
        </h2>
        <p>
          Apply once with your resume. We use AI to read it and suggest a match
          score, then a person reviews every application before any decision is
          made.
        </p>

        <div className="job-search">
          <Icon name="search" size={16} />
          <label htmlFor="portal-search" className="sr-only">
            Search open roles
          </label>
          <input
            id="portal-search"
            type="search"
            placeholder="Search by role or skill…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
      </section>

      <Notice icon="info" title="How your application is reviewed">
        Your resume text is matched against the role's required skills and
        description to produce a score out of 100. If you are invited to
        interview, you record short video answers and those are transcribed and
        scored against a written rubric. Every score shows the words it was
        based on, and a recruiter makes the final call — never the model alone.
      </Notice>

      <div className="section-heading">
        <div>
          <h2>{visible.length} open {visible.length === 1 ? "role" : "roles"}</h2>
          <p className="muted">Updated as teams publish new positions</p>
        </div>
      </div>

      {jobs.error ? (
        <ErrorState error={jobs.error} onRetry={jobs.reload} />
      ) : jobs.loading ? (
        <Panel>
          <Loading what="open roles" />
        </Panel>
      ) : visible.length === 0 ? (
        <Panel>
          <EmptyState title="No roles match your search">
            Try a different skill or clear the search box.
          </EmptyState>
        </Panel>
      ) : (
        <div className="job-list">
          {visible.map((job) => (
            <article className="job-card" key={job.id}>
              <span className="job-mark">
                <Icon name="briefcase" size={18} />
              </span>

              <div className="job-details">
                <h3>{job.title}</h3>
                <p>
                  {job.description?.slice(0, 150) || "No description provided"}
                  {job.description && job.description.length > 150 ? "…" : ""}
                </p>

                <div className="job-meta">
                  {job.minimum_experience > 0 ? (
                    <span>
                      <Icon name="clock" size={12} />
                      {job.minimum_experience}+ years
                    </span>
                  ) : null}
                  <span>
                    <Icon name="pin" size={12} />
                    Remote friendly
                  </span>
                  {job.interview_questions?.length ? (
                    <span>
                      <Icon name="mic" size={12} />
                      {job.interview_questions.length} video questions
                    </span>
                  ) : null}
                  {job.deadline ? (
                    <span>
                      <Icon name="calendar" size={12} />
                      Closes {formatDate(job.deadline)}
                    </span>
                  ) : null}
                </div>

                {job.required_skills?.length ? (
                  <div style={{ marginTop: 10 }}>
                    <SkillChips
                      skills={job.required_skills.slice(0, 6)}
                      tone="neutral"
                    />
                  </div>
                ) : null}
              </div>

              <button
                type="button"
                className="button button--primary"
                onClick={() => setApplyTo(job)}
              >
                Apply <Icon name="arrow-right" size={12} />
              </button>
            </article>
          ))}
        </div>
      )}

      <p className="candidate-footnote">
        We store your resume to assess this application. Scores are suggestions
        to help a recruiter read fairly — they are never the final word, and you
        can ask how any score about you was reached.
      </p>

      {applyTo ? (
        <ApplyModal job={applyTo} onClose={() => setApplyTo(null)} />
      ) : null}
    </div>
  );
}

const ACCEPTED =
  ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

function ApplyModal({ job, onClose }: { job: Job; onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const apply = useAction(api.applyToJob);

  async function submit(event: React.FormEvent) {
    event.preventDefault();

    if (!file) return;

    const result = await apply.run(job.id, file);

    if (result) setSubmitted(true);
  }

  if (submitted) {
    return (
      <Modal title="Application received" onClose={onClose}>
        <div className="profile-modal-head">
          <span className="evidence-check" style={{ width: 40, height: 40 }}>
            <Icon name="check" size={20} />
          </span>
          <div>
            <h2>Thanks — it's in</h2>
            <p className="muted">
              Your application for {job.title} has been received.
            </p>
          </div>
        </div>

        <p>
          Your resume is being read now. If it looks like a good match you will
          get an email with a link to record short video answers. A recruiter
          reviews every application either way.
        </p>

        <div className="modal-actions">
          <button
            type="button"
            className="button button--primary"
            onClick={onClose}
          >
            Done
          </button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title={`Apply: ${job.title}`} onClose={onClose}>
      <form className="form-stack" onSubmit={submit}>
        <p className="muted">
          One step: attach your resume. We read it to match against this role's
          requirements.
        </p>

        <label>
          Resume (PDF or DOCX)
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED}
            required
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <span className="privacy-note">
            Used to assess this application only. Nothing is shared outside the
            hiring team.
          </span>
        </label>

        {job.required_skills?.length ? (
          <div>
            <h3>What this role is matched on</h3>
            <SkillChips skills={job.required_skills} tone="neutral" />
            <p className="privacy-note">
              Listing relevant experience in your own words helps more than
              keyword stuffing — the match also reads your resume as a whole.
            </p>
          </div>
        ) : null}

        {apply.error ? (
          <div className="notice" role="alert">
            <Icon name="alert" size={16} />
            <div>
              <strong>Could not submit</strong>
              <p>{apply.error.message}</p>
            </div>
          </div>
        ) : null}

        <div className="modal-actions">
          <button
            type="button"
            className="button button--secondary"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="button button--primary"
            disabled={!file || apply.pending}
          >
            {apply.pending ? "Submitting…" : "Submit application"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

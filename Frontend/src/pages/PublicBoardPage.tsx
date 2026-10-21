/**
 * The public job board: open roles anyone can see without signing in.
 *
 * Browsing is open; only applying needs an account. "Apply" sends the visitor
 * to the candidate sign-in/sign-up, and a hiring-team sign-in link sits in the
 * header. Logged-in users never see this — they get their own workspace.
 */

import { useState } from "react";
import { api } from "../api/client";
import { useApi } from "../hooks/useApi";
import { Icon } from "../components/Icon";
import { SkillChips } from "../components/AiRecommendation";
import { formatDate } from "../lib/format";
import { EmptyState, ErrorState, Loading, Panel } from "../components/primitives";
import { goToEntry } from "../lib/entry";

export function PublicBoardPage() {
  const jobs = useApi(() => api.listJobs({ openOnly: true }), []);
  const [query, setQuery] = useState("");

  const term = query.toLowerCase();
  const visible = (jobs.data ?? []).filter((job) =>
    term
      ? `${job.title} ${job.description} ${job.required_skills.join(" ")}`
          .toLowerCase()
          .includes(term)
      : true,
  );

  return (
    <div className="public-board">
      <header className="public-topbar">
        <div className="login-brand">
          <span className="brand-mark">
            <Icon name="sparkles" size={18} />
          </span>
          <div>
            <strong>Hirewise</strong>
            <small>AI-assisted, human-decided hiring</small>
          </div>
        </div>
        <div className="public-topbar-actions">
          <button
            type="button"
            className="button button--secondary"
            onClick={() => goToEntry("apply")}
          >
            Candidate sign in
          </button>
          <button
            type="button"
            className="text-button"
            onClick={() => goToEntry("admin")}
          >
            Hiring team
          </button>
        </div>
      </header>

      <div className="candidate-portal">
        <section className="candidate-hero">
          <p className="eyebrow">OPEN ROLES</p>
          <h2>
            Find your next role, <span>fairly reviewed</span>
          </h2>
          <p>
            Browse every open role below. Applying takes one account so you can
            track where your application has reached — a person reviews every
            application before any decision is made.
          </p>

          <div className="job-search">
            <Icon name="search" size={16} />
            <label htmlFor="public-search" className="sr-only">
              Search open roles
            </label>
            <input
              id="public-search"
              type="search"
              placeholder="Search by role or skill…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
        </section>

        <div className="section-heading">
          <div>
            <h2>
              {visible.length} open {visible.length === 1 ? "role" : "roles"}
            </h2>
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
                  onClick={() => goToEntry("apply")}
                >
                  Apply <Icon name="arrow-right" size={12} />
                </button>
              </article>
            ))}
          </div>
        )}

        <p className="candidate-footnote">
          Scores are suggestions to help a recruiter read fairly — never the
          final word. You can ask how any score about you was reached.
        </p>
      </div>
    </div>
  );
}

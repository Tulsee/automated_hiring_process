/**
 * Roles, and the form to create one.
 *
 * Each card shows how many candidates it has drawn, so a role with no
 * applicants is visible at a glance.
 */

import { useMemo, useState } from "react";
import { api } from "../api/client";
import { useAction, useApi } from "../hooks/useApi";
import { Icon } from "../components/Icon";
import { SkillChips } from "../components/AiRecommendation";
import {
  ErrorState,
  Loading,
  Modal,
  Panel,
  StatusPill,
} from "../components/primitives";
import { PageHeader } from "../components/AppShell";
import type { Job } from "../types";

export function JobsPage({
  search,
  createOpen,
  onCreateOpenChange,
  onViewCandidates,
}: {
  search: string;
  createOpen: boolean;
  onCreateOpenChange: (open: boolean) => void;
  onViewCandidates: (jobId: string) => void;
}) {
  const jobs = useApi(() => api.listJobs(), []);
  const candidates = useApi(() => api.listCandidates({ limit: 200 }), []);

  const countsByJob = useMemo(() => {
    const counts = new Map<string, number>();

    for (const candidate of candidates.data?.candidates ?? []) {
      counts.set(candidate.job_id, (counts.get(candidate.job_id) ?? 0) + 1);
    }

    return counts;
  }, [candidates.data]);

  const visible = (jobs.data ?? []).filter((job) =>
    search
      ? `${job.title} ${job.description}`
          .toLowerCase()
          .includes(search.toLowerCase())
      : true,
  );

  return (
    <>
      <PageHeader
        eyebrow="ROLES"
        title="Open"
        highlight="roles"
        subtitle="Each role carries its own interview questions and scoring rubric."
        action={
          <button
            type="button"
            className="button button--primary"
            onClick={() => onCreateOpenChange(true)}
          >
            <Icon name="plus" size={14} /> New role
          </button>
        }
      />

      {jobs.error ? (
        <ErrorState error={jobs.error} onRetry={jobs.reload} />
      ) : jobs.loading ? (
        <Panel>
          <Loading what="roles" />
        </Panel>
      ) : visible.length === 0 ? (
        <Panel>
          <p className="muted">
            {search
              ? `No roles match "${search}".`
              : "No roles yet. Create one to start receiving applications."}
          </p>
        </Panel>
      ) : (
        <div className="job-grid">
          {visible.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              candidateCount={countsByJob.get(job.id) ?? 0}
              onViewCandidates={() => onViewCandidates(job.id)}
            />
          ))}
        </div>
      )}

      {createOpen ? (
        <CreateJobModal
          onClose={() => onCreateOpenChange(false)}
          onCreated={() => {
            onCreateOpenChange(false);
            jobs.reload();
          }}
        />
      ) : null}
    </>
  );
}

function JobCard({
  job,
  candidateCount,
  onViewCandidates,
}: {
  job: Job;
  candidateCount: number;
  onViewCandidates: () => void;
}) {
  const questionCount = job.interview_questions?.length ?? 0;

  return (
    <article className="job-card">
      <div className="job-card-top">
        <span className="job-mark">
          <Icon name="briefcase" size={18} />
        </span>
        <StatusPill value={candidateCount > 0 ? "published" : "draft"} />
      </div>

      <h3>{job.title}</h3>
      <p className="muted">
        {job.description?.slice(0, 110) || "No description"}
        {job.description && job.description.length > 110 ? "…" : ""}
      </p>

      {job.required_skills?.length ? (
        <div style={{ marginTop: 12 }}>
          <SkillChips skills={job.required_skills.slice(0, 5)} tone="neutral" />
        </div>
      ) : null}

      <div className="job-stats">
        <div>
          <strong>{candidateCount}</strong>
          <small>Candidates</small>
        </div>
        <div>
          <strong>{questionCount || "Default"}</strong>
          <small>{questionCount ? "Questions" : "Question set"}</small>
        </div>
        <div>
          <strong>{job.minimum_experience ?? 0}y</strong>
          <small>Min. experience</small>
        </div>
      </div>

      <button
        type="button"
        className="button button--secondary button--wide"
        onClick={onViewCandidates}
      >
        View candidates <Icon name="arrow-right" size={12} />
      </button>
    </article>
  );
}

function CreateJobModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [skills, setSkills] = useState("");
  const [minimumExperience, setMinimumExperience] = useState("0");

  const create = useAction(api.createJob);

  const canSubmit = title.trim().length > 0 && description.trim().length > 0;

  async function submit(event: React.FormEvent) {
    event.preventDefault();

    const result = await create.run({
      title: title.trim(),
      description: description.trim(),
      required_skills: skills
        .split(",")
        .map((skill) => skill.trim().toLowerCase())
        .filter(Boolean),
      minimum_experience: Number(minimumExperience) || 0,
    });

    if (result) onCreated();
  }

  return (
    <Modal title="Create a role" onClose={onClose}>
      <form className="form-stack" onSubmit={submit}>
        <label>
          Role title
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Backend Engineer"
            required
          />
        </label>

        <label>
          Description
          <textarea
            rows={4}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="What the person will work on, and what the team needs."
            required
          />
        </label>

        <label>
          Required skills
          <input
            value={skills}
            onChange={(event) => setSkills(event.target.value)}
            placeholder="python, fastapi, mongodb"
          />
          <span className="privacy-note">
            Comma separated. These are matched against the resume text to
            compute the skills part of the screening score.
          </span>
        </label>

        <label>
          Minimum years of experience
          <input
            type="number"
            min={0}
            step={0.5}
            value={minimumExperience}
            onChange={(event) => setMinimumExperience(event.target.value)}
          />
        </label>

        {create.error ? (
          <div className="notice" role="alert">
            <Icon name="alert" size={16} />
            <div>
              <strong>Could not create the role</strong>
              <p>{create.error.message}</p>
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
            disabled={!canSubmit || create.pending}
          >
            {create.pending ? "Creating…" : "Create role"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

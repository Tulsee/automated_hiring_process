/**
 * Changing a role after it exists.
 *
 * Only the fields a recruiter actually altered are sent, which is what the
 * API's PATCH expects: moving a deadline should not rewrite the questions, and
 * a question list resent unchanged would be indistinguishable from an edit in
 * the server log.
 *
 * Clearing a date sends an explicit `null`, since omitting the field means
 * "leave it alone".
 */

import { useState } from "react";
import { api } from "../api/client";
import { useAction, useApi } from "../hooks/useApi";
import { Icon } from "./Icon";
import { ErrorState, Loading, Modal, Notice } from "./primitives";
import { QuestionEditor } from "./QuestionEditor";
import { JobScheduleFields } from "./JobScheduleFields";
import {
  scheduleError,
  scheduleFromJob,
  type SchedulePatch,
} from "../lib/jobSchedule";
import { fromLocalInput } from "../lib/format";
import type { QuestionDraft } from "../lib/interview";
import type { Job, JobUpdate } from "../types";

/** The job's questions as editable drafts. */
function questionsFromJob(job: Job): QuestionDraft[] {
  return (job.interview_questions ?? []).map((question, index) => ({
    key: `existing-${index}`,
    text: question.text,
    competency: (question.competency ??
      "general") as QuestionDraft["competency"],
    time_limit_seconds: question.time_limit_seconds ?? 90,
  }));
}

/**
 * Loads the role fresh before editing it.
 *
 * The list it was opened from may be minutes old, and saving a stale copy
 * could quietly undo someone else's change — so the form is built from what
 * the server holds now, not from the row that was clicked.
 */
export function EditJobModal({
  job,
  onClose,
  onSaved,
}: {
  job: Job;
  onClose: () => void;
  onSaved: () => void;
}) {
  const current = useApi(() => api.getJob(job.id), [job.id]);

  if (current.loading) {
    return (
      <Modal title={`Edit: ${job.title}`} onClose={onClose}>
        <Loading what="this role" />
      </Modal>
    );
  }

  if (current.error) {
    return (
      <Modal title={`Edit: ${job.title}`} onClose={onClose}>
        <ErrorState error={current.error} onRetry={current.reload} />
      </Modal>
    );
  }

  return (
    <EditJobForm
      key={current.data!.updated_at ?? current.data!.id}
      job={current.data!}
      onClose={onClose}
      onSaved={onSaved}
    />
  );
}

function EditJobForm({
  job,
  onClose,
  onSaved,
}: {
  job: Job;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [title, setTitle] = useState(job.title);
  const [description, setDescription] = useState(job.description);
  const [skills, setSkills] = useState((job.required_skills ?? []).join(", "));
  const [minimumExperience, setMinimumExperience] = useState(
    String(job.minimum_experience ?? 0),
  );
  const [questions, setQuestions] = useState<QuestionDraft[]>(
    questionsFromJob(job),
  );
  const [schedule, setSchedule] = useState<SchedulePatch>(
    scheduleFromJob(job),
  );

  const save = useAction(api.updateJob);

  const original = scheduleFromJob(job);
  const originalSkills = (job.required_skills ?? []).join(", ");

  /** Only what changed, so the PATCH says what it means. */
  function buildPatch(): JobUpdate {
    const patch: JobUpdate = {};

    if (title !== job.title) patch.title = title.trim();

    if (description !== job.description) {
      patch.description = description.trim();
    }

    if (skills !== originalSkills) {
      patch.required_skills = skills
        .split(",")
        .map((skill) => skill.trim().toLowerCase())
        .filter(Boolean);
    }

    if (Number(minimumExperience) !== job.minimum_experience) {
      patch.minimum_experience = Number(minimumExperience) || 0;
    }

    const written = questions
      .filter((question) => question.text.trim().length > 0)
      .map((question) => ({
        text: question.text.trim(),
        competency: question.competency,
        time_limit_seconds: question.time_limit_seconds,
      }));

    const unchangedQuestions =
      JSON.stringify(written) ===
      JSON.stringify(
        questionsFromJob(job).map((question) => ({
          text: question.text,
          competency: question.competency,
          time_limit_seconds: question.time_limit_seconds,
        })),
      );

    if (!unchangedQuestions) patch.interview_questions = written;

    if (schedule.status !== original.status) patch.status = schedule.status;

    // An emptied field clears the date; `null` is meaningful here, so it is
    // sent rather than omitted.
    if (schedule.publishAt !== original.publishAt) {
      patch.publish_at = fromLocalInput(schedule.publishAt);
    }

    if (schedule.deadline !== original.deadline) {
      patch.deadline = fromLocalInput(schedule.deadline);
    }

    return patch;
  }

  const patch = buildPatch();
  const changeCount = Object.keys(patch).length;
  const error = scheduleError(schedule);

  return (
    <Modal title={`Edit: ${job.title}`} onClose={onClose}>
      <form
        className="form-stack"
        onSubmit={async (event) => {
          event.preventDefault();

          if (error || changeCount === 0) return;

          const updated = await save.run(job.id, patch);

          if (updated) onSaved();
        }}
      >
        <label>
          Role title
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            required
          />
        </label>

        <label>
          Description
          <textarea
            rows={4}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
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
            Comma separated. Changing these changes how future candidates are
            screened; scores already computed are not recalculated.
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

        <JobScheduleFields schedule={schedule} onChange={setSchedule} />

        <QuestionEditor questions={questions} onChange={setQuestions} />

        {questions.length > 0 &&
        questionsFromJob(job).length === 0 ? (
          <Notice icon="info" title="This role used the default questions">
            Saving these replaces the default set for candidates invited from
            now on. Interviews already created keep the questions they were
            given.
          </Notice>
        ) : null}

        {save.error ? (
          <Notice icon="alert" title="Could not save">
            {save.error.message}
          </Notice>
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
            disabled={Boolean(error) || changeCount === 0 || save.pending}
          >
            {save.pending
              ? "Saving…"
              : changeCount === 0
                ? "No changes"
                : `Save ${changeCount} ${changeCount === 1 ? "change" : "changes"}`}
          </button>
        </div>

        {changeCount > 0 && !error ? (
          <p className="helper-text">
            <Icon name="info" size={13} />
            <span>
              Sending only what changed: {Object.keys(patch).join(", ")}.
            </span>
          </p>
        ) : null}
      </form>
    </Modal>
  );
}

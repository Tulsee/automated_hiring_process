/**
 * A role's publication window: draft/published/closed, and the dates.
 *
 * Shared by the create and edit forms so both describe the window the same
 * way. The fields work in the viewer's local time and are converted to UTC on
 * the way out, because a recruiter typing "23:59" means their own evening.
 *
 * The effective state is previewed here rather than left to be discovered
 * after saving: "published" with a past deadline is closed, and a draft is
 * invisible whatever the dates say.
 */

import { Icon } from "./Icon";
import type { JobStatus } from "../types";
import {
  STATUS_CHOICES,
  previewState,
  scheduleError,
  type SchedulePatch,
} from "../lib/jobSchedule";

export function JobScheduleFields({
  schedule,
  onChange,
}: {
  schedule: SchedulePatch;
  onChange: (schedule: SchedulePatch) => void;
}) {
  const preview = previewState(schedule);
  const error = scheduleError(schedule);

  const scheduling = schedule.status === "published";

  return (
    <fieldset className="question-editor">
      <legend>Publication</legend>

      <label>
        Status
        <select
          value={schedule.status}
          onChange={(event) =>
            onChange({
              ...schedule,
              status: event.target.value as JobStatus,
            })
          }
        >
          {STATUS_CHOICES.map((choice) => (
            <option key={choice.id} value={choice.id}>
              {choice.label}
            </option>
          ))}
        </select>
        <span className="privacy-note">
          {STATUS_CHOICES.find((choice) => choice.id === schedule.status)?.hint}
        </span>
      </label>

      {scheduling ? (
        <div className="question-row-meta">
          <label>
            Publish at
            <input
              type="datetime-local"
              value={schedule.publishAt}
              onChange={(event) =>
                onChange({ ...schedule, publishAt: event.target.value })
              }
            />
            <span className="privacy-note">
              Leave empty to publish immediately.
            </span>
          </label>

          <label>
            Application deadline
            <input
              type="datetime-local"
              value={schedule.deadline}
              onChange={(event) =>
                onChange({ ...schedule, deadline: event.target.value })
              }
            />
            <span className="privacy-note">
              Leave empty for no closing date.
            </span>
          </label>
        </div>
      ) : null}

      {error ? (
        <p className="helper-text" role="alert" style={{ color: "var(--amber-ink)" }}>
          <Icon name="alert" size={13} />
          <span>{error}</span>
        </p>
      ) : (
        <p className="helper-text">
          <Icon name="info" size={13} />
          <span>
            <strong>{preview.state}.</strong> {preview.note} Times are in your
            own timezone.
          </span>
        </p>
      )}
    </fieldset>
  );
}

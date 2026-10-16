/**
 * A role's publication window, as the form works with it.
 *
 * Mirrors `app/services/job_lifecycle.py`: the status is the recruiter's
 * intent and the dates say when it takes effect, so the state an applicant
 * experiences is derived. Previewing it here lets the form explain itself
 * before anything is saved.
 */

import { parseApiDate } from "./format";
import type { JobStatus } from "../types";

export interface SchedulePatch {
  status: JobStatus;
  /** Values from `<input type="datetime-local">`, in the viewer's local time. */
  publishAt: string;
  deadline: string;
}

export const STATUS_CHOICES: { id: JobStatus; label: string; hint: string }[] = [
  {
    id: "draft",
    label: "Draft",
    hint: "Not visible to anyone. Nobody can apply.",
  },
  {
    id: "published",
    label: "Published",
    hint: "Visible and open, within the dates below.",
  },
  {
    id: "closed",
    label: "Closed",
    hint: "Visible to you, but no longer accepting applications.",
  },
];

export function previewState(
  schedule: SchedulePatch,
  now: Date = new Date(),
): { state: string; note: string } {
  if (schedule.status === "draft") {
    return { state: "Draft", note: "Nobody can see or apply to this role." };
  }

  if (schedule.status === "closed") {
    return {
      state: "Closed",
      note: "Applications are refused, whatever the dates say.",
    };
  }

  const publishAt = schedule.publishAt ? new Date(schedule.publishAt) : null;
  const deadline = schedule.deadline ? new Date(schedule.deadline) : null;

  if (publishAt && now < publishAt) {
    return {
      state: "Scheduled",
      note: `Hidden until ${publishAt.toLocaleString()}, then open.`,
    };
  }

  if (deadline && now > deadline) {
    return {
      state: "Closed",
      note: `The deadline passed on ${deadline.toLocaleString()}, so this role is already closed.`,
    };
  }

  if (deadline) {
    return {
      state: "Open",
      note: `Open now, closing ${deadline.toLocaleString()}.`,
    };
  }

  return { state: "Open", note: "Open now, with no closing date." };
}

/** The one combination the API rejects outright. */
export function scheduleError(schedule: SchedulePatch): string | null {
  if (!schedule.publishAt || !schedule.deadline) return null;

  if (new Date(schedule.deadline) <= new Date(schedule.publishAt)) {
    return "The deadline must be after the publish date, otherwise the role would never be open.";
  }

  return null;
}

/** An existing job's schedule, as form values. */
export function scheduleFromJob(job: {
  status: JobStatus;
  publish_at: string | null;
  deadline: string | null;
}): SchedulePatch {
  const toInput = (value: string | null) => {
    const date = parseApiDate(value);

    if (!date) return "";

    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);

    return local.toISOString().slice(0, 16);
  };

  return {
    status: job.status,
    publishAt: toInput(job.publish_at),
    deadline: toInput(job.deadline),
  };
}

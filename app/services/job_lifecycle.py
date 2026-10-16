"""When a job is open, and who may see it.

A job carries two different things:

* `status` - what the recruiter *intends*: a draft, published, or closed.
* `publish_at` / `deadline` - *when* that intent takes effect.

The state an applicant experiences is derived from both plus the clock, so it
is computed rather than stored. Storing it would mean a job silently staying
"open" until something happened to run a job that closed it; deriving it means
a deadline takes effect the moment it passes, with nothing scheduled.

    draft       never visible, whatever the dates say
    scheduled   published, but publish_at is still in the future
    open        published, publishing has happened, deadline has not passed
    expired     published, but the deadline has passed
    closed      closed by hand, before any deadline
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# What a recruiter sets.
STATUS_DRAFT = "draft"
STATUS_PUBLISHED = "published"
STATUS_CLOSED = "closed"

SETTABLE_STATUSES = {STATUS_DRAFT, STATUS_PUBLISHED, STATUS_CLOSED}

# What an applicant experiences.
STATE_DRAFT = "draft"
STATE_SCHEDULED = "scheduled"
STATE_OPEN = "open"
STATE_EXPIRED = "expired"
STATE_CLOSED = "closed"

# Jobs created before this module existed carry no status. They were visible
# and accepting applications, so that is what they keep meaning.
DEFAULT_STATUS = STATUS_PUBLISHED


def to_naive_utc(value: datetime | None) -> datetime | None:
    """Normalise a datetime to naive UTC.

    The rest of the codebase stores naive UTC (`datetime.utcnow()`), and
    comparing an aware datetime with a naive one raises `TypeError`. A client
    is free to send `2026-11-01T12:00:00+05:45`, so offsets are converted here
    rather than left to blow up at the comparison.
    """
    if value is None:
        return None

    if value.tzinfo is None:
        return value

    return value.astimezone(timezone.utc).replace(tzinfo=None)


def job_state(job: dict, now: datetime | None = None) -> str:
    """The state an applicant would experience for this job."""
    now = now or datetime.utcnow()

    status = job.get("status") or DEFAULT_STATUS

    if status == STATUS_DRAFT:
        return STATE_DRAFT

    if status == STATUS_CLOSED:
        return STATE_CLOSED

    publish_at = to_naive_utc(job.get("publish_at"))

    if publish_at is not None and now < publish_at:
        return STATE_SCHEDULED

    deadline = to_naive_utc(job.get("deadline"))

    if deadline is not None and now > deadline:
        return STATE_EXPIRED

    return STATE_OPEN


def is_open(job: dict, now: datetime | None = None) -> bool:
    """May this job be seen and applied to right now?"""
    return job_state(job, now) == STATE_OPEN


def closed_reason(job: dict, now: datetime | None = None) -> str:
    """Why an application was refused, in words an applicant can act on."""
    state = job_state(job, now)

    if state == STATE_DRAFT:
        return "This role is not published yet."

    if state == STATE_SCHEDULED:
        publish_at = to_naive_utc(job.get("publish_at"))

        return (
            "This role opens for applications on "
            f"{publish_at:%d %b %Y %H:%M} UTC."
        )

    if state == STATE_EXPIRED:
        deadline = to_naive_utc(job.get("deadline"))

        return (
            "Applications for this role closed on "
            f"{deadline:%d %b %Y %H:%M} UTC."
        )

    if state == STATE_CLOSED:
        return "This role is no longer accepting applications."

    return "This role is open."


class ScheduleError(ValueError):
    """The publish/deadline pair does not describe a usable window."""


def validate_schedule(
    publish_at: datetime | None, deadline: datetime | None
) -> None:
    """A deadline before publishing would open and close in the same instant."""
    publish_at = to_naive_utc(publish_at)
    deadline = to_naive_utc(deadline)

    if publish_at is not None and deadline is not None and deadline <= publish_at:
        raise ScheduleError(
            "The deadline must be after the publish date, otherwise the role "
            "would never be open."
        )

"""Creating interview sessions and their invite links.

Both the API route and the screening graph's invite node create sessions, so
the logic lives here rather than in either caller.
"""

import logging
from datetime import datetime

from bson import ObjectId

from app.core.config import settings
from app.db.mongodb import (
    candidates_collection,
    interview_sessions_collection,
    jobs_collection,
)
from app.models.interview_session import create_interview_session_document
from app.services.interview_questions import get_questions_for_job

logger = logging.getLogger(__name__)

# The canonical decision for a candidate who passed screening.
DECISION_INVITED_TO_INTERVIEW = "invited_to_interview"

# The screening graph historically wrote "invite_to_interview", so candidates
# already in the database carry either spelling.
ELIGIBLE_DECISIONS = {
    DECISION_INVITED_TO_INTERVIEW,
    "invite_to_interview",
}


def build_invite_url(invite_token: str) -> str:
    """The candidate-facing link for an invite token."""
    return f"{settings.APP_BASE_URL.rstrip('/')}/interview?token={invite_token}"


def is_eligible_for_interview(candidate: dict) -> bool:
    return candidate.get("decision") in ELIGIBLE_DECISIONS


def invite_is_expired(session: dict, now: datetime | None = None) -> bool:
    expires_at = session.get("invite_expires_at")

    if not expires_at:
        return False

    return (now or datetime.utcnow()) > expires_at


async def create_session_for_candidate(candidate: dict) -> dict:
    """Create a session for an invited candidate and return it with its link.

    The questions come from the candidate's job, so every candidate for that
    job answers the same ordered set.
    """
    candidate_id = str(candidate["_id"])

    job_id = str(candidate["job_id"])

    job = None

    if ObjectId.is_valid(job_id):
        job = await jobs_collection.find_one({"_id": ObjectId(job_id)})

    questions = get_questions_for_job(job)

    session = create_interview_session_document(
        candidate_id=candidate_id,
        job_id=job_id,
        questions=questions,
    )

    result = await interview_sessions_collection.insert_one(session)

    session_id = str(result.inserted_id)

    invite_url = build_invite_url(session["invite_token"])

    # Write the session back onto the candidate so it is discoverable from a
    # candidate listing, whoever created it.
    await candidates_collection.update_one(
        {"_id": candidate["_id"]},
        {
            "$set": {
                "interview_session_id": session_id,
                "interview_invite_url": invite_url,
                "interview_invite_expires_at": session["invite_expires_at"],
                "updated_at": datetime.utcnow(),
            }
        },
    )

    logger.info(
        "Interview session created: %s (candidate %s, %d questions)",
        session_id,
        candidate_id,
        len(questions),
    )

    return {
        "session_id": session_id,
        "session": session,
        "questions": questions,
        "invite_token": session["invite_token"],
        "invite_url": invite_url,
    }

"""The final, post-interview decision - the human's call, and what follows it.

The screening graph (app/agent/graph.py) decides who is *invited* to interview.
This module is the other end: once an interview is scored, a person decides the
outcome. The model only ever *suggests*; the decision is recorded against the
candidate, the right email is generated, and the application reaches its
outcome.

Kept separate from the LangGraph wiring so it can be read, tested and reused on
its own - the graph's apply node and the REST fallback both call `apply_decision`,
so there is exactly one place that records a decision and sends its email.
"""

import logging
from datetime import datetime

from bson import ObjectId

from app.db.mongodb import (
    candidates_collection,
    interview_sessions_collection,
    jobs_collection,
)
from app.services.email_service import send_decision_email
from app.services.notifications import KIND_APPLICATION, notify

logger = logging.getLogger(__name__)

# The outcomes a reviewer can land on. Stored in `final_decision`, distinct from
# the screening `decision` (invited_to_interview / reject) so neither overwrites
# the other and the application journey can read both.
FINAL_HIRE = "hired"
FINAL_NEXT_ROUND = "next_round"
FINAL_REJECT = "rejected"

FINAL_DECISIONS = {FINAL_HIRE, FINAL_NEXT_ROUND, FINAL_REJECT}

# What a reviewer does with the suggestion.
ACTION_APPROVE = "approve"  # accept the model's suggestion
ACTION_OVERRIDE = "override"  # record a different decision
ACTION_ANOTHER_LOOK = "another_look"  # not yet - leave it pending

# Overall interview percentage boundaries for the *suggestion* only. A person
# can always override; these just pre-fill a sensible starting point.
HIRE_THRESHOLD = 75.0
CONSIDER_THRESHOLD = 55.0


def suggest_decision(scorecard: dict | None) -> dict:
    """A starting-point recommendation from the scorecard - never the last word.

    Returns the suggested final decision and a one-line reason a reviewer can
    read, plus whether the scorecard itself asks for a human look.
    """
    if not scorecard:
        return {
            "decision": None,
            "reason": "No scorecard yet - score the interview before deciding.",
            "needs_human_review": True,
        }

    percent = scorecard.get("overall_percent")
    needs_review = bool(scorecard.get("needs_human_review"))

    if percent is None:
        return {
            "decision": None,
            "reason": "The interview produced no overall score; decide by hand.",
            "needs_human_review": True,
        }

    if percent >= HIRE_THRESHOLD:
        decision, reason = (
            FINAL_HIRE,
            f"Strong interview ({percent:.0f}/100).",
        )
    elif percent >= CONSIDER_THRESHOLD:
        decision, reason = (
            FINAL_NEXT_ROUND,
            f"A solid interview ({percent:.0f}/100) worth a further round.",
        )
    else:
        decision, reason = (
            FINAL_REJECT,
            f"The interview scored below the bar ({percent:.0f}/100).",
        )

    if needs_review:
        reason += " Flagged for review, so check the evidence before confirming."

    return {
        "decision": decision,
        "reason": reason,
        "needs_human_review": needs_review,
    }


async def gather_review(candidate_id: str) -> dict:
    """Everything a reviewer (or the graph) needs to decide one candidate.

    One source of truth for 'what does this interview say and what does the
    model suggest', used by both the LangGraph gather node and the REST path.
    """
    candidate = await candidates_collection.find_one(
        {"_id": ObjectId(candidate_id)}
    )
    if not candidate:
        raise ValueError(f"Candidate not found: {candidate_id}")

    job = await jobs_collection.find_one({"_id": ObjectId(candidate["job_id"])})
    job_title = job["title"] if job else "the role"

    session = await interview_sessions_collection.find_one(
        {"candidate_id": candidate_id}
    )
    scorecard = (session or {}).get("scorecard")

    suggestion = suggest_decision(scorecard)

    return {
        "candidate_id": candidate_id,
        "job_id": candidate["job_id"],
        "job_title": job_title,
        "candidate_name": candidate.get("name"),
        "candidate_email": candidate.get("email"),
        "session_id": str(session["_id"]) if session else None,
        "overall_percent": (scorecard or {}).get("overall_percent"),
        "needs_human_review": suggestion["needs_human_review"],
        "suggested_decision": suggestion["decision"],
        "suggested_reason": suggestion["reason"],
    }


def resolve_decision(action: str, suggested: str | None, override: str | None) -> str | None:
    """The decision an action lands on: the suggestion, an override, or none."""
    if action == ACTION_ANOTHER_LOOK:
        return None

    if action == ACTION_OVERRIDE:
        if override not in FINAL_DECISIONS:
            raise ValueError(
                f"Override needs a decision, one of: {sorted(FINAL_DECISIONS)}"
            )
        return override

    if action == ACTION_APPROVE:
        if suggested not in FINAL_DECISIONS:
            raise ValueError(
                "There is no suggestion to approve; override with an explicit "
                "decision instead."
            )
        return suggested

    raise ValueError(f"Unknown action '{action}'")


def _message_for(decision: str, reviewer: str | None, note: str | None) -> str:
    base = {
        FINAL_HIRE: "Advanced to an offer after interview review.",
        FINAL_NEXT_ROUND: "Moving to a further interview round.",
        FINAL_REJECT: "Not progressing after interview review.",
    }[decision]

    if note:
        base += f" Reviewer note: {note.strip()}"

    return base


async def apply_decision(
    candidate_id: str,
    decision: str,
    reviewer: str | None = None,
    note: str | None = None,
) -> dict:
    """Record a final decision against the candidate and send its email.

    The single place a decision is committed: it writes the outcome to Mongo,
    generates and sends the matching email, and records whether that email went
    out - so the decision stands even if the mail server is down.
    """
    if decision not in FINAL_DECISIONS:
        raise ValueError(f"Unknown decision '{decision}'")

    candidate = await candidates_collection.find_one({"_id": ObjectId(candidate_id)})

    if not candidate:
        raise ValueError(f"Candidate not found: {candidate_id}")

    job = await jobs_collection.find_one({"_id": ObjectId(candidate["job_id"])})
    job_title = job["title"] if job else "the role"

    message = _message_for(decision, reviewer, note)
    now = datetime.utcnow()

    await candidates_collection.update_one(
        {"_id": candidate["_id"]},
        {
            "$set": {
                "final_decision": decision,
                "final_decision_message": message,
                "final_decided_by": reviewer,
                "final_decided_at": now,
                "updated_at": now,
            }
        },
    )

    email_status = "skipped"
    email_error = None

    candidate_email = candidate.get("email")

    if candidate_email:
        try:
            await send_decision_email(
                decision=decision,
                candidate_email=candidate_email,
                candidate_name=candidate.get("name"),
                job_title=job_title,
            )
            email_status = "sent"
        except Exception as error:  # noqa: BLE001 - record, do not fail the decision
            logger.error("Decision email failed for %s: %s", candidate_id, error)
            email_status = "failed"
            email_error = str(error)
    else:
        email_error = "Candidate email not found"
        logger.warning(
            "No email for candidate %s; decision recorded without one.", candidate_id
        )

    await candidates_collection.update_one(
        {"_id": candidate["_id"]},
        {
            "$set": {
                "final_decision_email_status": email_status,
                "final_decision_email_error": email_error,
            }
        },
    )

    # Tell the candidate (if they have an account) where their application landed.
    titles = {
        FINAL_HIRE: "You've been selected",
        FINAL_NEXT_ROUND: "You're moving to the next round",
        FINAL_REJECT: "An update on your application",
    }
    await notify(
        candidate.get("applicant_user_id"),
        KIND_APPLICATION,
        f"{titles[decision]} — {job_title}",
        message,
    )

    return {
        "candidate_id": candidate_id,
        "final_decision": decision,
        "message": message,
        "email_status": email_status,
    }


async def review_and_apply(
    candidate_id: str,
    action: str,
    override: str | None = None,
    note: str | None = None,
    reviewer: str | None = None,
) -> dict:
    """Decide a candidate without the graph - the plain path, and the fallback.

    Mirrors the graph (gather the suggestion, resolve the action to a decision,
    apply it) for when a paused run has been lost, e.g. after a restart.
    """
    review = await gather_review(candidate_id)

    decision = resolve_decision(action, review["suggested_decision"], override)

    if decision is None:
        return {
            "candidate_id": candidate_id,
            "action": action,
            "final_decision": None,
            "message": "Held for another look; no decision recorded yet.",
        }

    result = await apply_decision(candidate_id, decision, reviewer, note)

    return {
        "candidate_id": candidate_id,
        "action": action,
        "final_decision": decision,
        "message": result["message"],
    }

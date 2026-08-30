import logging
from bson import ObjectId
from typing import TypedDict
logger = logging.getLogger(__name__)

from langgraph.graph import StateGraph, START, END

from app.db.mongodb import candidates_collection, jobs_collection
from app.services.email_service import (
    send_rejection_email,
    send_interview_invitation_email,
)

logging.basicConfig(level=logging.INFO)


# graph state
class HiringState(TypedDict):
    candidate_id: str
    job_id: str
    job_title: str

    candidate_name: str | None
    candidate_email: str | None

    screening_score: float | None
    screening_rationale: str | None

    decision: str
    message: str


SCREENING_THRESHOLD = 70.0


async def screening_node(state: HiringState) -> HiringState:
    logger.info(f"screening_node: state entering node: {state}")

    candidate_id = state["candidate_id"]

    logger.info(f"screening_node: screening candidate_id: {candidate_id}")

    candidate = await candidates_collection.find_one({"_id": ObjectId(candidate_id)})

    if not candidate:
        logger.error(f"screening_node: candidate not found: {candidate_id}")
        raise ValueError(f"Candidate not found: {candidate_id}")

    job = await jobs_collection.find_one({"_id": ObjectId(candidate["job_id"])})

    if not job:
        raise ValueError(f"Job {candidate['job_id']} not found")

    screening_score = candidate.get("screening_score")

    if screening_score is None:
        raise ValueError("Candidate has not been screened yet")

    screening_rationale = candidate.get("screening_rationale")

    logger.info(f"screening_node: candidate screening_score: {screening_score}")

    return {
        **state,
        "job_id": candidate["job_id"],
        "job_title": job["title"],
        "candidate_name": candidate.get("name"),
        "candidate_email": candidate.get("email"),
        "screening_score": screening_score,
        "screening_rationale": screening_rationale,
    }


# conditional routing function
def route_after_screening(state: HiringState) -> str:
    score = state["screening_score"]

    if score is None:
        raise ValueError("Screening score is missing")

    logger.info(f"\n Routing candidate with score: {score}")

    if score >= SCREENING_THRESHOLD:
        return "invite"

    return "reject"


# Reject node
async def reject_node(state: HiringState) -> HiringState:

    logger.info(" Candidate routed to rejection path")

    decision = "reject"

    message = (
        f"Candidate scored "
        f"{state['screening_score']:.1f}/100 "
        f"and did not meet the minimum "
        f"screening threshold of "
        f"{SCREENING_THRESHOLD}."
    )

    await candidates_collection.update_one(
        {"_id": ObjectId(state["candidate_id"])},
        {
            "$set": {
                "decision": decision,
                "decision_message": message,
            }
        },
    )

    # Send rejection email
    if state.get("candidate_email"):

        try:
            await send_rejection_email(
                candidate_email=state["candidate_email"],
                candidate_name=state.get("candidate_name"),
                job_title=state["job_title"],
            )

            await candidates_collection.update_one(
                {"_id": ObjectId(state["candidate_id"])},
                {
                    "$set": {
                        "decision_email_status": "sent",
                        "decision_email_error": None,
                    }
                },
            )

        except Exception as e:

            logger.error(f" Rejection email failed: {e}")

            await candidates_collection.update_one(
                {"_id": ObjectId(state["candidate_id"])},
                {
                    "$set": {
                        "decision_email_status": "failed",
                        "decision_email_error": str(e),
                    }
                },
            )
    else:
        logger.warning("Candidate email not available. " "Skipping rejection email.")

        await candidates_collection.update_one(
            {"_id": ObjectId(state["candidate_id"])},
            {
                "$set": {
                    "decision_email_status": "skipped",
                    "decision_email_error": ("Candidate email not found"),
                }
            },
        )
    return {**state, "decision": "reject", "message": message}


# Invite node
async def invite_node(state: HiringState) -> HiringState:

    logger.info(" Candidate routed to interview path")

    decision = "invite_to_interview"

    message = (
        f"Candidate scored "
        f"{state['screening_score']:.1f}/100 "
        f"and passed the screening threshold."
    )

    await candidates_collection.update_one(
        {"_id": ObjectId(state["candidate_id"])},
        {
            "$set": {
                "decision": decision,
                "decision_message": message,
            }
        },
    )

    # Send interview invitation email
    if state.get("candidate_email"):
        try:
            await send_interview_invitation_email(
                candidate_email=state["candidate_email"],
                candidate_name=state.get("candidate_name"),
                job_title=state["job_title"],
            )

            await candidates_collection.update_one(
                {"_id": ObjectId(state["candidate_id"])},
                {
                    "$set": {
                        "decision_email_status": "sent",
                        "decision_email_error": None,
                    }
                },
            )

        except Exception as e:
            logger.error(f"Interview email failed: {e}")

            await candidates_collection.update_one(
                {"_id": ObjectId(state["candidate_id"])},
                {
                    "$set": {
                        "decision_email_status": "failed",
                        "decision_email_error": str(e),
                    }
                },
            )

    else:
        logger.warning("Candidate email not available. " "Skipping interview email.")

        await candidates_collection.update_one(
            {"_id": ObjectId(state["candidate_id"])},
            {
                "$set": {
                    "decision_email_status": "skipped",
                    "decision_email_error": ("Candidate email not found"),
                }
            },
        )

    return {**state, "decision": "invite_to_interview", "message": message}


# Build graph
graph_builder = StateGraph(HiringState)


# Nodes
graph_builder.add_node(
    "screening",
    screening_node,
)

graph_builder.add_node(
    "reject",
    reject_node,
)

graph_builder.add_node(
    "invite",
    invite_node,
)


# Start
graph_builder.add_edge(
    START,
    "screening",
)


# Conditional routing
graph_builder.add_conditional_edges(
    "screening",
    route_after_screening,
    {
        "reject": "reject",
        "invite": "invite",
    },
)


# End paths
graph_builder.add_edge(
    "reject",
    END,
)

graph_builder.add_edge(
    "invite",
    END,
)


graph = graph_builder.compile()

import logging
from bson import ObjectId
from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from app.db.mongodb import candidates_collection

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)


# graph state
class HiringState(TypedDict):
    candidate_id: str
    job_id: str

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

    screening_score = candidate.get("screening_score")

    if screening_score is None:
        raise ValueError("Candidate has not been screened yet")

    screening_rationale = candidate.get("screening_rationale")

    logger.info(f"screening_node: candidate screening_score: {screening_score}")

    return {
        **state,
        "job_id": candidate["job_id"],
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

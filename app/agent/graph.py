import logging
from typing import TypedDict

from langgraph.graph import StateGraph, START, END

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)

SCREENING_THRESHOLD = 70.0


# graph state
class HiringState(TypedDict):
    candidate_id: str
    job_id: str

    candidate_name: str | None
    candidate_email: str | None

    screening_score: float | None
    screening_rational: str | None

    decision: str
    message: str


def screening_node(state: HiringState) -> HiringState:
    logger.info(f"screening_node: state entering node: {state}")

    score = state["screening_score"]

    logger.info(f"screening_node: screening score: {score}")

    return {**state, "screening_score": score}


def route_after_screening(state: HiringState) -> str:
    score = state["screening_score"]

    logger.info(f"\n Routing candidate with score: {score}")

    if score >= SCREENING_THRESHOLD:
        return "invite"

    return "reject"


def reject_node(state: HiringState) -> HiringState:

    logger.info(" Candidate routed to rejection path")

    return {
        **state,
        "decision": "reject",
        "message": ("Candidate did not meet the " "screening threshold."),
    }


def invite_node(state: HiringState) -> HiringState:

    logger.info(" Candidate routed to interview path")

    return {
        **state,
        "decision": "invite_to_interview",
        "message": (
            "Candidate passed screening " "and should be invited to interview."
        ),
    }


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

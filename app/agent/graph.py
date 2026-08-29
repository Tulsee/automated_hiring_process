import logging
from typing import TypedDict

from langgraph.graph import StateGraph, START, END

logger = logging.getLogger(__name__)


# graph state
class HiringState(TypedDict):
    candidate_name: str
    message: str


# node
def process_candidate(state: HiringState) -> HiringState:
    logger.info(f"state entering node: {state}")
    updated_state = {
        "candidate_name": state["candidate_name"],
        "message": (
            f"Hello {state['candidate_name']}," "Your application has been received."
        ),
    }
    print(f"state leaving node: {updated_state}")
    logger.info(f"state leaving node: {updated_state}")
    return updated_state


# build the graph
graph_builder = StateGraph(HiringState)

graph_builder.add_node("process_candidate", process_candidate)

graph_builder.add_edge(START, "process_candidate")

graph_builder.add_edge("process_candidate", END)

graph = graph_builder.compile()

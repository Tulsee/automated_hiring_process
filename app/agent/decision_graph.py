"""Module 17: the final decision as an interruptible LangGraph.

Where the screening graph runs start-to-finish, this one **pauses**. It gathers
the interview result, then hits `interrupt()` and waits - nothing is accepted or
rejected until a person resumes it with their call. That durable pause is the
concept the module is about: the graph holds its place (in the checkpointer)
between the reviewer opening the candidate and clicking a decision.

    gather  ->  human_review (interrupt!)  ->  apply  ->  END

The checkpointer is in-process, so a paused graph lives as long as the server
does; the authoritative outcome is still written to Mongo by `apply_decision`,
so a decision survives a restart even though a *mid-flight pause* would not. The
REST layer falls back to applying directly if a pause is lost.
"""

import logging
from typing import TypedDict
from uuid import uuid4

from bson import ObjectId
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

try:  # langgraph >= 1.x
    from langgraph.checkpoint.memory import InMemorySaver as _MemorySaver
except ImportError:  # pragma: no cover - older naming
    from langgraph.checkpoint.memory import MemorySaver as _MemorySaver

from app.db.mongodb import candidates_collection
from app.services.decision import (
    ACTION_ANOTHER_LOOK,
    apply_decision,
    gather_review,
    resolve_decision,
)

logger = logging.getLogger(__name__)


class DecisionState(TypedDict, total=False):
    candidate_id: str
    job_id: str
    job_title: str
    candidate_name: str | None
    candidate_email: str | None
    session_id: str | None

    overall_percent: float | None
    needs_human_review: bool
    suggested_decision: str | None
    suggested_reason: str | None

    # Filled in on resume.
    action: str
    reviewer: str | None
    note: str | None
    decision: str | None
    message: str | None


async def gather_node(state: DecisionState) -> DecisionState:
    """Load the candidate, their interview scorecard, and a suggested outcome."""
    return {**state, **(await gather_review(state["candidate_id"]))}


async def human_review_node(state: DecisionState) -> DecisionState:
    """Pause for a person. Resumes with {action, decision?, note?, reviewer?}."""
    resumed = interrupt(
        {
            "candidate_id": state["candidate_id"],
            "candidate_name": state.get("candidate_name"),
            "job_title": state.get("job_title"),
            "overall_percent": state.get("overall_percent"),
            "needs_human_review": state.get("needs_human_review"),
            "suggested_decision": state.get("suggested_decision"),
            "suggested_reason": state.get("suggested_reason"),
        }
    )

    action = resumed.get("action")
    decision = resolve_decision(
        action=action,
        suggested=state.get("suggested_decision"),
        override=resumed.get("decision"),
    )

    return {
        **state,
        "action": action,
        "reviewer": resumed.get("reviewer"),
        "note": resumed.get("note"),
        "decision": decision,
    }


async def apply_node(state: DecisionState) -> DecisionState:
    """Commit the reviewer's call: record it and send the matching email."""
    action = state.get("action")

    if action == ACTION_ANOTHER_LOOK or state.get("decision") is None:
        message = "Held for another look; no decision recorded yet."
        logger.info("Candidate %s held for another look.", state["candidate_id"])
        return {**state, "decision": None, "message": message}

    result = await apply_decision(
        candidate_id=state["candidate_id"],
        decision=state["decision"],
        reviewer=state.get("reviewer"),
        note=state.get("note"),
    )

    return {**state, "message": result["message"]}


def _build_graph():
    builder = StateGraph(DecisionState)

    builder.add_node("gather", gather_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("apply", apply_node)

    builder.add_edge(START, "gather")
    builder.add_edge("gather", "human_review")
    builder.add_edge("human_review", "apply")
    builder.add_edge("apply", END)

    # An in-process checkpointer: it holds each paused run for the life of the
    # server, which is what lets the graph resume from exactly where it stopped.
    return builder.compile(checkpointer=_MemorySaver())


decision_graph = _build_graph()


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _interrupt_value(result: dict):
    """The payload of the first pending interrupt in a run result, if any."""
    pending = result.get("__interrupt__")

    if not pending:
        return None

    first = pending[0]

    return getattr(first, "value", first)


async def start_decision_review(candidate_id: str) -> dict:
    """Run the graph up to its human pause and return the review payload.

    A fresh thread id per call, stored on the candidate, so each review is its
    own run and a 'take another look' can be followed by a clean restart.
    """
    thread_id = f"decision:{candidate_id}:{uuid4().hex[:8]}"

    await candidates_collection.update_one(
        {"_id": ObjectId(candidate_id)},
        {"$set": {"decision_thread_id": thread_id, "decision_status": "in_review"}},
    )

    result = await decision_graph.ainvoke(
        {"candidate_id": candidate_id}, _config(thread_id)
    )

    review = _interrupt_value(result)

    if review is None:
        # No pause means the graph ran to the end without a human - unexpected
        # here, but surface the final state rather than a confusing empty body.
        raise ValueError("The decision graph did not pause for review")

    return {"thread_id": thread_id, "review": review}


async def resume_decision(
    thread_id: str,
    action: str,
    decision: str | None = None,
    note: str | None = None,
    reviewer: str | None = None,
) -> dict:
    """Resume a paused review with the reviewer's call and return the outcome."""
    result = await decision_graph.ainvoke(
        Command(
            resume={
                "action": action,
                "decision": decision,
                "note": note,
                "reviewer": reviewer,
            }
        ),
        _config(thread_id),
    )

    return {
        "candidate_id": result["candidate_id"],
        "action": action,
        "final_decision": result.get("decision"),
        "message": result.get("message"),
    }

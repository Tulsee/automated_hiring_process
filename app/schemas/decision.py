"""Request and response shapes for the final, post-interview decision."""

from pydantic import BaseModel, Field


class DecisionReview(BaseModel):
    """What the reviewer is shown before deciding."""

    candidate_id: str
    candidate_name: str | None = None
    job_title: str | None = None
    overall_percent: float | None = None
    needs_human_review: bool = False
    suggested_decision: str | None = None
    suggested_reason: str | None = None


class DecisionReviewResponse(BaseModel):
    # The handle for the paused graph run, echoed back when the decision is made.
    thread_id: str
    review: DecisionReview


class DecisionRequest(BaseModel):
    # approve | override | another_look
    action: str = Field(..., example="approve")
    # Required for an override: hired | next_round | rejected.
    decision: str | None = None
    note: str | None = None
    # The paused run to resume; omit to decide without a prior review call.
    thread_id: str | None = None


class DecisionResult(BaseModel):
    candidate_id: str
    action: str
    final_decision: str | None = None
    message: str | None = None

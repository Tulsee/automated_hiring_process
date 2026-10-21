import logging

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_permission

from app.agent.graph import graph
from app.agent.decision_graph import resume_decision, start_decision_review
from app.schemas.decision import (
    DecisionRequest,
    DecisionResult,
    DecisionReview,
    DecisionReviewResponse,
)
from app.services.decision import review_and_apply

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/hiring",
    tags=["Hiring"],
)


@router.post(
    "/candidates/{candidate_id}/screen",
    dependencies=[Depends(require_permission("candidates:screen"))],
)
async def screen_candidate(
    candidate_id: str,
):

    if not ObjectId.is_valid(candidate_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid candidate ID",
        )

    initial_state = {
        "candidate_id": candidate_id,
        "job_id": "",
        "candidate_name": None,
        "candidate_email": None,
        "screening_score": None,
        "screening_rationale": None,
        "decision": None,
        "message": None,
    }

    try:

        result = await graph.ainvoke(initial_state)

        return {
            "candidate_id": candidate_id,
            "decision": result["decision"],
            "screening_score": result["screening_score"],
            "rationale": result["screening_rationale"],
            "message": result["message"],
        }

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# --------------------------------------------------- final decision (Module 17/18)

@router.post(
    "/candidates/{candidate_id}/decision/review",
    response_model=DecisionReviewResponse,
    dependencies=[Depends(require_permission("interviews:read"))],
)
async def start_candidate_decision_review(candidate_id: str):
    """Open the final-decision review: run the graph to its human pause.

    Returns the model's suggestion and a `thread_id` that resumes this exact
    paused run when the reviewer makes the call.
    """
    if not ObjectId.is_valid(candidate_id):
        raise HTTPException(status_code=400, detail="Invalid candidate ID")

    try:
        started = await start_decision_review(candidate_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return DecisionReviewResponse(
        thread_id=started["thread_id"],
        review=DecisionReview(**started["review"]),
    )


@router.post(
    "/candidates/{candidate_id}/decision",
    response_model=DecisionResult,
)
async def decide_candidate(
    candidate_id: str,
    body: DecisionRequest,
    actor: dict = Depends(require_permission("interviews:score")),
):
    """Make the final call - resuming the paused graph, recording it, emailing.

    Resumes the interrupted run named by `thread_id`. If that run is gone (the
    server restarted since the review opened) it falls back to deciding
    directly, so the decision is never blocked by a lost in-memory pause.
    """
    if not ObjectId.is_valid(candidate_id):
        raise HTTPException(status_code=400, detail="Invalid candidate ID")

    reviewer = actor.get("email")

    try:
        if body.thread_id:
            try:
                result = await resume_decision(
                    thread_id=body.thread_id,
                    action=body.action,
                    decision=body.decision,
                    note=body.note,
                    reviewer=reviewer,
                )
            except Exception as error:  # noqa: BLE001 - lost pause -> decide directly
                logger.warning(
                    "Could not resume decision thread %s (%s); deciding directly.",
                    body.thread_id,
                    error,
                )
                result = await review_and_apply(
                    candidate_id=candidate_id,
                    action=body.action,
                    override=body.decision,
                    note=body.note,
                    reviewer=reviewer,
                )
        else:
            result = await review_and_apply(
                candidate_id=candidate_id,
                action=body.action,
                override=body.decision,
                note=body.note,
                reviewer=reviewer,
            )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return DecisionResult(**result)

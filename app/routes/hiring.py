from bson import ObjectId
from fastapi import APIRouter, HTTPException

from app.agent.graph import graph

router = APIRouter(
    prefix="/hiring",
    tags=["Hiring"],
)


@router.post("/candidates/{candidate_id}/screen")
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

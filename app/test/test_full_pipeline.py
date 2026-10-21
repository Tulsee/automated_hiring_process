"""Module 19 integration test: one application through the whole pipeline.

It walks a single candidate from intake all the way to the final decision,
across the two real graphs (screening and decision) and the real routes, and
shows the headline property of Module 17 - the pipeline **pauses for a human**
at the end, and only a person's action produces an outcome.

The interview recording/transcription/scoring in the middle needs Ollama and
whisper, which a unit test cannot run; that stage is represented by the scored
session it would produce, so the orchestration either side is exercised for
real.
"""

from datetime import datetime

from bson import ObjectId

from app.services.application_journey import journey_summary


def _seed_job(fakes):
    job = {
        "_id": ObjectId(),
        "title": "Backend Engineer",
        "status": "published",
        "required_skills": ["python", "fastapi"],
        "interview_questions": [
            {"id": "q1", "text": "Tell us about an API you built.", "competency": "technical"},
        ],
    }
    fakes.jobs.documents.append(job)
    return job


def _seed_screened_candidate(fakes, job, score):
    candidate = {
        "_id": ObjectId(),
        "job_id": str(job["_id"]),
        "name": "Grace Hopper",
        "email": "grace@example.com",
        "status": "processed",
        "screening_score": score,
        "screening_rationale": f"Scored {score} against the role.",
        "decision": None,
    }
    fakes.candidates.documents.append(candidate)
    return candidate


async def test_one_application_flows_through_to_a_paused_human_decision(client, fakes):
    job = _seed_job(fakes)
    candidate = _seed_screened_candidate(fakes, job, score=85.0)
    cid = str(candidate["_id"])

    # 1. Screen: the screening graph invites a strong candidate and creates
    #    their interview session.
    screen = await client.post(f"/hiring/candidates/{cid}/screen")
    assert screen.status_code == 200
    assert screen.json()["decision"] == "invited_to_interview"
    assert candidate["decision"] == "invited_to_interview"

    session = await fakes.sessions.find_one({"candidate_id": cid})
    assert session is not None

    # 2. Interview recorded, transcribed and scored: represented by the scored
    #    session those stages produce.
    await fakes.sessions.update_one(
        {"_id": session["_id"]},
        {
            "$set": {
                "status": "submitted",
                "scoring_status": "completed",
                "scorecard": {"overall_percent": 88.0, "needs_human_review": False},
                "scored_at": datetime.utcnow(),
            }
        },
    )

    # 3. Decision review: the graph runs to the human pause and suggests an
    #    outcome, without deciding anything yet.
    review = (await client.post(f"/hiring/candidates/{cid}/decision/review")).json()
    assert review["review"]["suggested_decision"] == "hired"
    assert candidate.get("final_decision") is None  # still paused

    # 4. The human makes the call, which resumes the graph and closes the loop.
    decided = await client.post(
        f"/hiring/candidates/{cid}/decision",
        json={"action": "approve", "thread_id": review["thread_id"]},
    )
    assert decided.status_code == 200
    assert decided.json()["final_decision"] == "hired"

    # 5. The outcome is recorded, the email generated, and the candidate's
    #    journey now shows the outcome reached.
    assert candidate["final_decision"] == "hired"
    assert fakes.decision_emails[-1]["decision"] == "hired"

    summary = journey_summary(candidate, session)
    outcome = next(step for step in summary["steps"] if step["key"] == "outcome")
    assert outcome["state"] == "done"


async def test_a_weak_candidate_is_rejected_at_screening(client, fakes):
    job = _seed_job(fakes)
    candidate = _seed_screened_candidate(fakes, job, score=40.0)
    cid = str(candidate["_id"])

    screen = await client.post(f"/hiring/candidates/{cid}/screen")

    assert screen.status_code == 200
    assert screen.json()["decision"] == "reject"
    # No interview session is created for a screen-rejected candidate.
    assert await fakes.sessions.find_one({"candidate_id": cid}) is None

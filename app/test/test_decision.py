"""The final, post-interview decision: suggestion, the graph pause, and apply.

Covers Module 17 (the interrupt-and-resume) and Module 18 (recording the
decision and generating the right email).
"""

from datetime import datetime

import pytest
from bson import ObjectId

from app.agent.decision_graph import resume_decision, start_decision_review
from app.services.decision import (
    FINAL_HIRE,
    FINAL_NEXT_ROUND,
    FINAL_REJECT,
    resolve_decision,
    suggest_decision,
)


def scorecard(percent, needs_review=False):
    return {"overall_percent": percent, "needs_human_review": needs_review}


class TestSuggestion:
    def test_a_strong_interview_suggests_hire(self):
        assert suggest_decision(scorecard(90))["decision"] == FINAL_HIRE

    def test_a_middling_interview_suggests_another_round(self):
        assert suggest_decision(scorecard(60))["decision"] == FINAL_NEXT_ROUND

    def test_a_weak_interview_suggests_reject(self):
        assert suggest_decision(scorecard(30))["decision"] == FINAL_REJECT

    def test_no_scorecard_makes_no_suggestion_and_asks_for_review(self):
        result = suggest_decision(None)

        assert result["decision"] is None
        assert result["needs_human_review"] is True

    def test_a_flagged_scorecard_still_suggests_but_flags_review(self):
        result = suggest_decision(scorecard(90, needs_review=True))

        assert result["decision"] == FINAL_HIRE
        assert result["needs_human_review"] is True
        assert "review" in result["reason"].lower()


class TestResolveDecision:
    def test_approve_takes_the_suggestion(self):
        assert resolve_decision("approve", FINAL_HIRE, None) == FINAL_HIRE

    def test_override_takes_the_explicit_decision(self):
        assert resolve_decision("override", FINAL_HIRE, FINAL_REJECT) == FINAL_REJECT

    def test_another_look_lands_on_no_decision(self):
        assert resolve_decision("another_look", FINAL_HIRE, None) is None

    def test_override_without_a_decision_is_rejected(self):
        with pytest.raises(ValueError):
            resolve_decision("override", FINAL_HIRE, None)

    def test_approving_nothing_is_rejected(self):
        with pytest.raises(ValueError):
            resolve_decision("approve", None, None)


def _seed_scored_candidate(fakes, percent=90.0, needs_review=False):
    job = {"_id": ObjectId(), "title": "Backend Engineer"}
    fakes.jobs.documents.append(job)

    candidate = {
        "_id": ObjectId(),
        "job_id": str(job["_id"]),
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "decision": "invited_to_interview",
    }
    fakes.candidates.documents.append(candidate)

    fakes.sessions.documents.append(
        {
            "_id": ObjectId(),
            "candidate_id": str(candidate["_id"]),
            "status": "submitted",
            "scorecard": {
                "overall_percent": percent,
                "needs_human_review": needs_review,
            },
        }
    )

    return candidate


class TestDecisionGraph:
    """The graph pauses at the human step and resumes with the decision."""

    async def test_the_graph_pauses_for_a_human(self, fakes):
        candidate = _seed_scored_candidate(fakes, percent=90.0)

        started = await start_decision_review(str(candidate["_id"]))

        review = started["review"]
        assert review["suggested_decision"] == FINAL_HIRE
        assert review["candidate_name"] == "Ada Lovelace"
        # No decision has been written while the graph is paused.
        assert candidate.get("final_decision") is None

    async def test_resuming_with_approve_records_and_emails(self, fakes):
        candidate = _seed_scored_candidate(fakes, percent=90.0)

        started = await start_decision_review(str(candidate["_id"]))
        result = await resume_decision(
            thread_id=started["thread_id"], action="approve", reviewer="boss@x.com"
        )

        assert result["final_decision"] == FINAL_HIRE
        assert candidate["final_decision"] == FINAL_HIRE
        assert candidate["final_decided_by"] == "boss@x.com"
        assert fakes.decision_emails[-1]["decision"] == FINAL_HIRE

    async def test_overriding_the_suggestion_is_honoured(self, fakes):
        candidate = _seed_scored_candidate(fakes, percent=90.0)

        started = await start_decision_review(str(candidate["_id"]))
        result = await resume_decision(
            thread_id=started["thread_id"],
            action="override",
            decision=FINAL_REJECT,
            note="Concerns about the evidence",
        )

        assert result["final_decision"] == FINAL_REJECT
        assert candidate["final_decision"] == FINAL_REJECT
        assert "Concerns" in candidate["final_decision_message"]

    async def test_another_look_records_nothing_and_sends_no_email(self, fakes):
        candidate = _seed_scored_candidate(fakes, percent=90.0)

        started = await start_decision_review(str(candidate["_id"]))
        result = await resume_decision(
            thread_id=started["thread_id"], action="another_look"
        )

        assert result["final_decision"] is None
        assert candidate.get("final_decision") is None
        assert fakes.decision_emails == []


class TestDecisionRoutes:
    async def test_review_then_decide_over_http(self, client, fakes):
        candidate = _seed_scored_candidate(fakes, percent=90.0)
        cid = str(candidate["_id"])

        review = (
            await client.post(f"/hiring/candidates/{cid}/decision/review")
        ).json()

        assert review["review"]["suggested_decision"] == FINAL_HIRE
        thread_id = review["thread_id"]

        decided = await client.post(
            f"/hiring/candidates/{cid}/decision",
            json={"action": "approve", "thread_id": thread_id},
        )

        assert decided.status_code == 200
        assert decided.json()["final_decision"] == FINAL_HIRE
        assert candidate["final_decision"] == FINAL_HIRE

    async def test_deciding_without_a_thread_falls_back_to_direct(
        self, client, fakes
    ):
        # No prior review call and no thread id: the route decides directly.
        candidate = _seed_scored_candidate(fakes, percent=30.0)
        cid = str(candidate["_id"])

        decided = await client.post(
            f"/hiring/candidates/{cid}/decision",
            json={"action": "approve"},
        )

        assert decided.status_code == 200
        assert decided.json()["final_decision"] == FINAL_REJECT

    async def test_a_lost_thread_still_decides(self, client, fakes):
        # A thread id the in-memory checkpointer has never seen (as after a
        # restart): the route falls back rather than failing.
        candidate = _seed_scored_candidate(fakes, percent=90.0)
        cid = str(candidate["_id"])

        decided = await client.post(
            f"/hiring/candidates/{cid}/decision",
            json={"action": "approve", "thread_id": "decision:gone:deadbeef"},
        )

        assert decided.status_code == 200
        assert decided.json()["final_decision"] == FINAL_HIRE

    async def test_an_invalid_candidate_id_is_rejected(self, client, fakes):
        response = await client.post(
            "/hiring/candidates/not-an-id/decision",
            json={"action": "approve"},
        )

        assert response.status_code == 400

"""Tests for scorecard aggregation and the scoring endpoints (Module 16).

The arithmetic is tested directly, because the promise of this module is that
anyone can recompute the overall score by hand from what the scorecard reports.
"""

from datetime import datetime

import pytest
from bson import ObjectId

from app.routes import interviews
from app.services.answer_scoring_service import (
    SCORE_FLAG_EMPTY,
    SCORE_FLAG_OFF_TOPIC,
    SCORE_FLAG_UNVERIFIED_QUOTE,
)
from app.services.rubric import get_rubric_for_job
from app.services.scorecard_service import (
    FLAG_NOT_TRANSCRIBED,
    FLAG_UNANSWERED,
    build_scorecard,
    to_percent,
    weighted_overall,
)

QUESTIONS = [
    {
        "id": "q_tech",
        "text": "Your backend experience?",
        "competency": "technical_depth",
        "time_limit_seconds": 60,
    },
    {
        "id": "q_design",
        "text": "Design a scalable API.",
        "competency": "system_design",
        "time_limit_seconds": 90,
    },
    {
        "id": "q_problem",
        "text": "A hard problem you solved?",
        "competency": "problem_solving",
        "time_limit_seconds": 120,
    },
]


def answer_score(question_id, competency, score, **extra):
    return {
        "question_id": question_id,
        "competency": competency,
        "score": score,
        "evidence_quote": "I build REST APIs in Python",
        "quote_verified": True,
        "reasoning": "Concrete hands-on detail.",
        "answers_question": True,
        "flags": [],
        **extra,
    }


def make_session(fakes, status="submitted", questions=None):
    session = {
        "_id": ObjectId(),
        "candidate_id": str(ObjectId()),
        "job_id": str(ObjectId()),
        "questions": [
            dict(q) for q in (QUESTIONS if questions is None else questions)
        ],
        "current_question_index": 2,
        "total_time_seconds": 270,
        "status": status,
        "created_at": datetime.utcnow(),
    }
    fakes.sessions.documents.append(session)
    return session


def add_answer(fakes, session_id, question_id, index, transcript="word " * 20, **extra):
    answer = {
        "_id": ObjectId(),
        "session_id": session_id,
        "question_id": question_id,
        "question_index": index,
        "file_path": f"uploads/{question_id}.webm",
        "transcript": transcript.strip(),
        "transcription_status": "completed",
        **extra,
    }
    fakes.answers.documents.append(answer)
    return answer


@pytest.fixture
def stub_scorer(monkeypatch):
    """Score every answer 4, with a verifiable quote."""
    calls = []

    async def fake(transcript, question, rubric, client=None):
        calls.append(question["id"])

        from app.services.rubric import entry_for_competency

        return {
            "competency": entry_for_competency(
                rubric, question.get("competency")
            )["competency"],
            "score": 4,
            "evidence_quote": transcript[:20],
            "quote_verified": True,
            "reasoning": "Solid, specific answer.",
            "answers_question": True,
            "flags": [],
            "model": "stub",
        }

    monkeypatch.setattr(interviews, "score_answer", fake)

    return calls


class TestWeightedArithmetic:
    def test_percent_maps_the_1_to_5_scale_onto_0_to_100(self):
        assert to_percent(1) == 0.0
        assert to_percent(3) == 50.0
        assert to_percent(5) == 100.0
        assert to_percent(None) is None

    def test_the_overall_score_is_the_weighted_mean(self):
        competencies = [
            {"competency": "a", "score": 5.0, "weight": 0.5},
            {"competency": "b", "score": 3.0, "weight": 0.5},
        ]

        overall, workings = weighted_overall(competencies)

        assert overall == 4.0
        assert workings["competencies_used"] == 2

    def test_weighting_actually_changes_the_result(self):
        """A weight that does nothing is not a weight."""
        heavy_on_a = [
            {"competency": "a", "score": 5.0, "weight": 0.9},
            {"competency": "b", "score": 1.0, "weight": 0.1},
        ]

        overall, _ = weighted_overall(heavy_on_a)

        assert overall == pytest.approx(4.6)

    def test_the_reported_weights_reproduce_the_score(self):
        """The whole promise of Module 16: recomputable by hand."""
        competencies = [
            {"competency": "a", "score": 4.0, "weight": 0.35},
            {"competency": "b", "score": 2.0, "weight": 0.35},
            {"competency": "c", "score": 5.0, "weight": 0.30},
        ]

        overall, workings = weighted_overall(competencies)

        by_hand = sum(
            entry["score"] * workings["weights"][entry["competency"]]
            for entry in competencies
        )

        assert overall == pytest.approx(by_hand, abs=0.01)

    def test_an_unscored_competency_is_excluded_and_its_weight_redistributed(
        self,
    ):
        """An unscoreable answer must not silently drag the score to zero."""
        competencies = [
            {"competency": "a", "score": 4.0, "weight": 0.5},
            {"competency": "b", "score": None, "weight": 0.5},
        ]

        overall, workings = weighted_overall(competencies)

        assert overall == 4.0
        assert workings["excluded"] == ["b"]
        assert workings["weights"] == {"a": 1.0}

    def test_no_scores_at_all_gives_no_overall(self):
        overall, workings = weighted_overall(
            [{"competency": "a", "score": None, "weight": 1.0}]
        )

        assert overall is None
        assert workings["competencies_used"] == 0

    def test_zero_weights_fall_back_to_an_unweighted_mean(self):
        competencies = [
            {"competency": "a", "score": 2.0, "weight": 0},
            {"competency": "b", "score": 4.0, "weight": 0},
        ]

        overall, _ = weighted_overall(competencies)

        assert overall == 3.0


class TestBuildScorecard:
    def test_reports_per_competency_and_overall_scores(self):
        rubric = get_rubric_for_job(None)

        scores = [
            answer_score("q_tech", "technical_depth", 5),
            answer_score("q_design", "system_design", 3),
            answer_score("q_problem", "problem_solving", 4),
        ]

        scorecard = build_scorecard({}, rubric, scores)

        assert len(scorecard["competency_scores"]) == 3
        # 5*0.35 + 3*0.35 + 4*0.30 = 4.0
        assert scorecard["overall_score"] == pytest.approx(4.0)
        assert scorecard["overall_percent"] == 75.0
        assert scorecard["answers_scored"] == 3

    def test_competencies_are_reported_in_rubric_order(self):
        rubric = get_rubric_for_job(None)

        scores = [
            answer_score("q_problem", "problem_solving", 4),
            answer_score("q_tech", "technical_depth", 5),
            answer_score("q_design", "system_design", 3),
        ]

        scorecard = build_scorecard({}, rubric, scores)

        assert [c["competency"] for c in scorecard["competency_scores"]] == [
            "technical_depth",
            "system_design",
            "problem_solving",
        ]

    def test_every_score_carries_its_evidence(self):
        rubric = get_rubric_for_job(None)

        scorecard = build_scorecard(
            {}, rubric, [answer_score("q_tech", "technical_depth", 5)]
        )

        evidence = scorecard["competency_scores"][0]["evidence"][0]

        assert evidence["quote"] == "I build REST APIs in Python"
        assert evidence["quote_verified"] is True
        assert evidence["reasoning"]

    def test_the_rubric_is_included_so_scores_can_be_checked(self):
        rubric = get_rubric_for_job(None)

        scorecard = build_scorecard(
            {}, rubric, [answer_score("q_tech", "technical_depth", 5)]
        )

        assert len(scorecard["rubric"]) == 3
        assert scorecard["rubric"][0]["descriptors"]["5"]

    def test_several_answers_for_one_competency_are_averaged(self):
        rubric = get_rubric_for_job(None)

        scores = [
            answer_score("q1", "technical_depth", 5),
            answer_score("q2", "technical_depth", 3),
        ]

        scorecard = build_scorecard({}, rubric, scores)

        assert scorecard["competency_scores"][0]["score"] == 4.0
        assert scorecard["competency_scores"][0]["answers_scored"] == 2


class TestReviewFlags:
    def test_a_clean_interview_needs_no_review(self):
        rubric = get_rubric_for_job(None)

        scores = [
            answer_score("q_tech", "technical_depth", 5),
            answer_score("q_design", "system_design", 4),
            answer_score("q_problem", "problem_solving", 4),
        ]

        scorecard = build_scorecard({}, rubric, scores)

        assert scorecard["needs_human_review"] is False
        assert scorecard["review_items"] == []

    @pytest.mark.parametrize(
        "flag",
        [
            SCORE_FLAG_EMPTY,
            SCORE_FLAG_OFF_TOPIC,
            SCORE_FLAG_UNVERIFIED_QUOTE,
            FLAG_UNANSWERED,
            FLAG_NOT_TRANSCRIBED,
        ],
    )
    def test_each_problem_flag_triggers_review(self, flag):
        rubric = get_rubric_for_job(None)

        scores = [
            answer_score("q_tech", "technical_depth", 4),
            answer_score("q_design", "system_design", 4, flags=[flag]),
            answer_score("q_problem", "problem_solving", 4),
        ]

        scorecard = build_scorecard({}, rubric, scores)

        assert scorecard["needs_human_review"] is True
        assert flag in scorecard["flags"]
        assert scorecard["review_items"][0]["question_id"] == "q_design"

    def test_an_interview_with_nothing_scored_needs_review(self):
        rubric = get_rubric_for_job(None)

        scores = [
            answer_score("q_tech", "technical_depth", None, flags=[FLAG_UNANSWERED])
        ]

        scorecard = build_scorecard({}, rubric, scores)

        assert scorecard["overall_score"] is None
        assert scorecard["needs_human_review"] is True


class TestScoreSessionEndpoint:
    async def test_scores_a_whole_interview(self, client, fakes, stub_scorer):
        session = make_session(fakes)
        session_id = str(session["_id"])

        for index, question in enumerate(QUESTIONS):
            add_answer(fakes, session_id, question["id"], index)

        response = await client.post(f"/interviews/sessions/{session_id}/score")

        assert response.status_code == 200
        body = response.json()

        assert body["scoring_status"] == "completed"
        assert body["scorecard"]["overall_score"] == 4.0
        assert body["scorecard"]["answers_scored"] == 3
        assert len(body["answer_scores"]) == 3
        assert len(stub_scorer) == 3

    async def test_the_scorecard_is_stored_on_the_session(
        self, client, fakes, stub_scorer
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "q_tech", 0)

        await client.post(f"/interviews/sessions/{session_id}/score")

        assert session["scorecard"]["overall_score"] == 4.0
        assert session["scoring_status"] == "partial"
        assert isinstance(session["scored_at"], datetime)

    async def test_an_unanswered_question_is_reported_not_skipped(
        self, client, fakes, stub_scorer
    ):
        """A scorecard must cover the whole interview."""
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "q_tech", 0)

        body = (
            await client.post(f"/interviews/sessions/{session_id}/score")
        ).json()

        assert body["scorecard"]["questions_total"] == 3
        assert body["scorecard"]["answers_scored"] == 1
        assert FLAG_UNANSWERED in body["scorecard"]["flags"]
        assert body["scorecard"]["needs_human_review"] is True

    async def test_an_untranscribed_answer_is_flagged(
        self, client, fakes, stub_scorer
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(
            fakes,
            session_id,
            "q_tech",
            0,
            transcription_status="pending",
        )

        body = (
            await client.post(f"/interviews/sessions/{session_id}/score")
        ).json()

        assert FLAG_NOT_TRANSCRIBED in body["scorecard"]["flags"]
        assert stub_scorer == []

    async def test_rescoring_reuses_stored_scores(
        self, client, fakes, stub_scorer
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "q_tech", 0)

        await client.post(f"/interviews/sessions/{session_id}/score")
        await client.post(f"/interviews/sessions/{session_id}/score")

        # The expensive model call happened once.
        assert len(stub_scorer) == 1

    async def test_force_rescores(self, client, fakes, stub_scorer):
        session = make_session(fakes)
        session_id = str(session["_id"])

        add_answer(fakes, session_id, "q_tech", 0)

        await client.post(f"/interviews/sessions/{session_id}/score")
        await client.post(f"/interviews/sessions/{session_id}/score?force=true")

        assert len(stub_scorer) == 2

    async def test_a_session_without_questions_is_rejected(self, client, fakes):
        session = make_session(fakes, questions=[])

        response = await client.post(
            f"/interviews/sessions/{session['_id']}/score"
        )

        assert response.status_code == 400

    async def test_a_broken_job_rubric_is_rejected(self, client, fakes):
        """Falling back to a different rubric would score candidates
        inconsistently, so this fails loudly instead."""
        job_id = ObjectId()
        fakes.jobs.documents.append(
            {
                "_id": job_id,
                "interview_rubric": [{"competency": "only_one"}],
            }
        )

        session = make_session(fakes)
        session["job_id"] = str(job_id)

        add_answer(fakes, str(session["_id"]), "q_tech", 0)

        response = await client.post(
            f"/interviews/sessions/{session['_id']}/score"
        )

        assert response.status_code == 400
        assert "rubric" in response.json()["detail"].lower()

    async def test_rejects_an_unknown_session(self, client):
        response = await client.post(f"/interviews/sessions/{ObjectId()}/score")

        assert response.status_code == 404


class TestGetScorecard:
    async def test_returns_the_stored_scorecard(
        self, client, fakes, stub_scorer
    ):
        session = make_session(fakes)
        session_id = str(session["_id"])

        for index, question in enumerate(QUESTIONS):
            add_answer(fakes, session_id, question["id"], index)

        await client.post(f"/interviews/sessions/{session_id}/score")

        response = await client.get(
            f"/interviews/sessions/{session_id}/scorecard"
        )

        assert response.status_code == 200
        body = response.json()

        assert body["scorecard"]["overall_score"] == 4.0
        assert len(body["scorecard"]["competency_scores"]) == 3
        assert len(body["answer_scores"]) == 3

    async def test_an_unscored_session_says_so(self, client, fakes):
        session = make_session(fakes)

        response = await client.get(
            f"/interviews/sessions/{session['_id']}/scorecard"
        )

        assert response.status_code == 404
        assert "not been scored" in response.json()["detail"]

    async def test_rejects_an_unknown_session(self, client):
        response = await client.get(
            f"/interviews/sessions/{ObjectId()}/scorecard"
        )

        assert response.status_code == 404

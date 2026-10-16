"""Tests for the rubric and per-answer scoring (Module 15).

The model is stubbed; what is tested for real is the part that keeps scoring
honest - that a rubric is well-formed, and that an evidence quote is actually
present in the transcript rather than taken on trust.
"""

import pytest

from app.services.answer_scoring_service import (
    MIN_SCOREABLE_WORDS,
    SCORE_FLAG_EMPTY,
    SCORE_FLAG_NO_QUOTE,
    SCORE_FLAG_OFF_TOPIC,
    SCORE_FLAG_SCORING_FAILED,
    SCORE_FLAG_TOO_SHORT,
    SCORE_FLAG_UNVERIFIED_QUOTE,
    clamp_score,
    score_answer,
    verify_quote,
)
from app.services.rubric import (
    DEFAULT_RUBRIC,
    MAX_COMPETENCIES,
    MIN_COMPETENCIES,
    RubricError,
    entry_for_competency,
    format_descriptors,
    get_rubric_for_job,
    validate_rubric,
)

TRANSCRIPT = (
    "I have five years of backend development experience. I mainly build "
    "REST APIs in Python using FastAPI, with MongoDB for storage. Recently I "
    "designed a service that handles about two thousand requests per second."
)

QUESTION = {
    "id": "question_1",
    "text": "Tell us about your backend experience.",
    "competency": "technical_depth",
    "time_limit_seconds": 60,
}


class FakeClient:
    """Stands in for ollama's AsyncClient."""

    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.calls = []

    async def chat(self, **kwargs):
        self.calls.append(kwargs)

        if self.error:
            raise self.error

        import json

        return {"message": {"content": json.dumps(self.payload)}}


def payload(**overrides):
    base = {
        "competency": "technical_depth",
        "score": 4,
        "evidence_quote": "I mainly build REST APIs in Python using FastAPI",
        "reasoning": "Describes concrete hands-on work with the relevant stack.",
        "answers_question": True,
    }
    base.update(overrides)
    return base


class TestRubricShape:
    def test_the_default_rubric_is_valid(self):
        rubric = get_rubric_for_job(None)

        assert MIN_COMPETENCIES <= len(rubric) <= MAX_COMPETENCIES

    def test_weights_sum_to_one(self):
        rubric = get_rubric_for_job(None)

        assert sum(entry["weight"] for entry in rubric) == pytest.approx(1.0)

    def test_every_competency_has_descriptors_for_1_3_and_5(self):
        """A score with no written standard behind it cannot be defended."""
        for entry in get_rubric_for_job(None):
            assert {1, 3, 5} <= set(entry["descriptors"])

    def test_too_few_competencies_is_rejected(self):
        with pytest.raises(RubricError, match="competencies"):
            validate_rubric(
                [{"competency": "a", "descriptors": {1: "x", 5: "y"}}]
            )

    def test_too_many_competencies_is_rejected(self):
        rubric = [
            {"competency": f"c{index}", "descriptors": {1: "x", 5: "y"}}
            for index in range(MAX_COMPETENCIES + 1)
        ]

        with pytest.raises(RubricError, match="competencies"):
            validate_rubric(rubric)

    def test_duplicate_competencies_are_rejected(self):
        rubric = [
            {"competency": "same", "descriptors": {1: "x", 5: "y"}},
            {"competency": "same", "descriptors": {1: "x", 5: "y"}},
            {"competency": "other", "descriptors": {1: "x", 5: "y"}},
        ]

        with pytest.raises(RubricError, match="Duplicate"):
            validate_rubric(rubric)

    def test_a_competency_without_descriptors_is_rejected(self):
        rubric = [
            {"competency": "a", "descriptors": {1: "x", 5: "y"}},
            {"competency": "b", "descriptors": {1: "x", 5: "y"}},
            {"competency": "c"},
        ]

        with pytest.raises(RubricError, match="descriptors"):
            validate_rubric(rubric)

    def test_weights_are_rescaled_rather_than_rejected(self):
        """Weights written as 2/3/5 should work without summing to 1."""
        rubric = validate_rubric(
            [
                {"competency": "a", "weight": 2, "descriptors": {1: "x", 5: "y"}},
                {"competency": "b", "weight": 3, "descriptors": {1: "x", 5: "y"}},
                {"competency": "c", "weight": 5, "descriptors": {1: "x", 5: "y"}},
            ]
        )

        assert sum(entry["weight"] for entry in rubric) == pytest.approx(1.0)
        assert rubric[2]["weight"] == pytest.approx(0.5)

    def test_missing_weights_become_equal(self):
        rubric = validate_rubric(
            [
                {"competency": "a", "descriptors": {1: "x", 5: "y"}},
                {"competency": "b", "descriptors": {1: "x", 5: "y"}},
                {"competency": "c", "descriptors": {1: "x", 5: "y"}},
            ]
        )

        assert [entry["weight"] for entry in rubric] == [
            pytest.approx(0.3333, abs=1e-3)
        ] * 3

    def test_string_descriptor_keys_from_json_are_accepted(self):
        rubric = validate_rubric(
            [
                {"competency": "a", "descriptors": {"1": "x", "5": "y"}},
                {"competency": "b", "descriptors": {"1": "x", "5": "y"}},
                {"competency": "c", "descriptors": {"1": "x", "5": "y"}},
            ]
        )

        assert rubric[0]["descriptors"][1] == "x"

    def test_a_job_can_define_its_own_rubric(self):
        job = {
            "interview_rubric": [
                {
                    "competency": "data_modelling",
                    "weight": 1,
                    "descriptors": {1: "poor", 3: "ok", 5: "great"},
                },
                {
                    "competency": "data_quality",
                    "weight": 1,
                    "descriptors": {1: "poor", 3: "ok", 5: "great"},
                },
                {
                    "competency": "communication",
                    "weight": 1,
                    "descriptors": {1: "poor", 3: "ok", 5: "great"},
                },
            ]
        }

        rubric = get_rubric_for_job(job)

        assert [entry["competency"] for entry in rubric] == [
            "data_modelling",
            "data_quality",
            "communication",
        ]

    def test_descriptors_render_in_ascending_order(self):
        rendered = format_descriptors(DEFAULT_RUBRIC[0])

        assert rendered.index("1 -") < rendered.index("3 -") < rendered.index("5 -")


class TestCompetencyLookup:
    def test_a_known_competency_resolves_to_its_row(self):
        entry = entry_for_competency(get_rubric_for_job(None), "system_design")

        assert entry["competency"] == "system_design"

    def test_an_unknown_competency_falls_back_to_general(self):
        """A job-specific question must never go silently unscored."""
        entry = entry_for_competency(get_rubric_for_job(None), "underwater_welding")

        assert entry["competency"] == "general"
        assert entry["descriptors"]

    def test_a_question_with_no_competency_falls_back_to_general(self):
        entry = entry_for_competency(get_rubric_for_job(None), None)

        assert entry["competency"] == "general"


class TestQuoteVerification:
    def test_an_exact_quote_verifies(self):
        assert verify_quote("I mainly build REST APIs in Python", TRANSCRIPT)

    def test_punctuation_and_casing_differences_still_verify(self):
        """The model tidies transcripts up; that is not fabrication."""
        assert verify_quote("i mainly build rest apis in python,", TRANSCRIPT)

    def test_extra_whitespace_still_verifies(self):
        assert verify_quote("I   mainly\nbuild REST APIs", TRANSCRIPT)

    def test_a_fabricated_quote_does_not_verify(self):
        """The whole point: an invented quote must be caught."""
        assert not verify_quote(
            "I led a team of fifteen engineers at Google", TRANSCRIPT
        )

    def test_a_reordered_quote_does_not_verify(self):
        assert not verify_quote("Python using build mainly I", TRANSCRIPT)

    def test_a_paraphrase_does_not_verify(self):
        assert not verify_quote(
            "He says he builds web services with Python frameworks", TRANSCRIPT
        )

    def test_an_empty_quote_does_not_verify(self):
        assert not verify_quote("", TRANSCRIPT)
        assert not verify_quote("   ", TRANSCRIPT)

    def test_a_punctuation_only_quote_does_not_verify(self):
        assert not verify_quote("...", TRANSCRIPT)


class TestClampScore:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (3, 3),
            ("4", 4),
            (4.4, 4),
            (0, 1),
            (9, 5),
            (-2, 1),
            (None, None),
            ("high", None),
        ],
    )
    def test_scores_are_coerced_into_the_scale(self, value, expected):
        assert clamp_score(value) == expected


class TestScoreAnswer:
    async def test_returns_a_quote_backed_score(self):
        client = FakeClient(payload())

        result = await score_answer(
            TRANSCRIPT, QUESTION, get_rubric_for_job(None), client=client
        )

        assert result["score"] == 4
        assert result["competency"] == "technical_depth"
        assert result["quote_verified"] is True
        assert result["flags"] == []
        assert result["reasoning"]

    async def test_the_rubric_descriptors_are_sent_to_the_model(self):
        client = FakeClient(payload())

        await score_answer(
            TRANSCRIPT, QUESTION, get_rubric_for_job(None), client=client
        )

        prompt = client.calls[0]["messages"][1]["content"]

        assert "RUBRIC (1-5)" in prompt
        assert "Technical depth" in prompt
        assert TRANSCRIPT in prompt

    async def test_an_unverifiable_quote_is_flagged(self):
        client = FakeClient(
            payload(evidence_quote="I led a team of fifteen engineers at Google")
        )

        result = await score_answer(
            TRANSCRIPT, QUESTION, get_rubric_for_job(None), client=client
        )

        assert result["quote_verified"] is False
        assert SCORE_FLAG_UNVERIFIED_QUOTE in result["flags"]

    async def test_a_missing_quote_is_flagged(self):
        client = FakeClient(payload(evidence_quote=""))

        result = await score_answer(
            TRANSCRIPT, QUESTION, get_rubric_for_job(None), client=client
        )

        assert SCORE_FLAG_NO_QUOTE in result["flags"]

    async def test_an_off_topic_answer_is_flagged(self):
        client = FakeClient(payload(answers_question=False))

        result = await score_answer(
            TRANSCRIPT, QUESTION, get_rubric_for_job(None), client=client
        )

        assert SCORE_FLAG_OFF_TOPIC in result["flags"]

    async def test_an_empty_answer_is_not_sent_to_the_model(self):
        client = FakeClient(payload())

        result = await score_answer(
            "", QUESTION, get_rubric_for_job(None), client=client
        )

        assert result["score"] is None
        assert result["flags"] == [SCORE_FLAG_EMPTY]
        assert client.calls == []

    async def test_a_very_short_answer_is_not_sent_to_the_model(self):
        client = FakeClient(payload())

        result = await score_answer(
            "Thank you very much.", QUESTION, get_rubric_for_job(None), client=client
        )

        assert result["score"] is None
        assert result["flags"] == [SCORE_FLAG_TOO_SHORT]
        assert client.calls == []

    async def test_the_short_answer_threshold_is_the_documented_one(self):
        client = FakeClient(payload())

        just_long_enough = " ".join(["word"] * MIN_SCOREABLE_WORDS)

        await score_answer(
            just_long_enough, QUESTION, get_rubric_for_job(None), client=client
        )

        assert len(client.calls) == 1

    async def test_a_model_failure_is_reported_not_raised(self):
        """One bad answer must not abandon a whole scorecard."""
        client = FakeClient(error=RuntimeError("ollama is down"))

        result = await score_answer(
            TRANSCRIPT, QUESTION, get_rubric_for_job(None), client=client
        )

        assert result["score"] is None
        assert SCORE_FLAG_SCORING_FAILED in result["flags"]
        assert "ollama is down" in result["reasoning"]

    async def test_malformed_model_json_is_reported_not_raised(self):
        class BadJson(FakeClient):
            async def chat(self, **kwargs):
                return {"message": {"content": "not json at all"}}

        result = await score_answer(
            TRANSCRIPT, QUESTION, get_rubric_for_job(None), client=BadJson()
        )

        assert result["score"] is None
        assert SCORE_FLAG_SCORING_FAILED in result["flags"]

    async def test_an_out_of_range_score_is_clamped(self):
        client = FakeClient(payload(score=99))

        result = await score_answer(
            TRANSCRIPT, QUESTION, get_rubric_for_job(None), client=client
        )

        assert result["score"] == 5

    async def test_a_question_competency_overrides_the_model_claim(self):
        """The model does not get to choose which competency it scored."""
        client = FakeClient(payload(competency="something_else"))

        result = await score_answer(
            TRANSCRIPT, QUESTION, get_rubric_for_job(None), client=client
        )

        assert result["competency"] == "technical_depth"

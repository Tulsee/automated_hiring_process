"""Module 16: aggregate per-answer scores into one explainable scorecard.

The aggregation is deliberately plain arithmetic: a weighted mean of the
per-competency scores, where every weight comes from the rubric and is reported
alongside the result. Anyone reading a scorecard can recompute the overall
number by hand, which is the point - an opaque aggregate cannot be argued with.

Nothing here decides anything. The scorecard reports scores, the evidence
behind them, and what a human should look at.
"""

import logging

from app.services.answer_scoring_service import (
    SCORE_FLAG_EMPTY,
    SCORE_FLAG_OFF_TOPIC,
    SCORE_FLAG_SCORING_FAILED,
    SCORE_FLAG_TOO_SHORT,
    SCORE_FLAG_UNVERIFIED_QUOTE,
)
from app.services.rubric import SCORE_MAX, SCORE_MIN

logger = logging.getLogger(__name__)

FLAG_UNANSWERED = "unanswered_question"
FLAG_NOT_TRANSCRIBED = "not_transcribed"
FLAG_NO_SCORES = "no_scores"

# Any of these on an answer means a person should look at it before the score
# is relied on.
REVIEW_FLAGS = {
    SCORE_FLAG_EMPTY,
    SCORE_FLAG_TOO_SHORT,
    SCORE_FLAG_OFF_TOPIC,
    SCORE_FLAG_UNVERIFIED_QUOTE,
    SCORE_FLAG_SCORING_FAILED,
    FLAG_UNANSWERED,
    FLAG_NOT_TRANSCRIBED,
    FLAG_NO_SCORES,
}


def to_percent(score: float | None) -> float | None:
    """A 1-5 score as 0-100, so it reads next to the screening score."""
    if score is None:
        return None

    span = SCORE_MAX - SCORE_MIN

    return round(((score - SCORE_MIN) / span) * 100, 1)


def aggregate_competency(competency: str, entry: dict, answers: list[dict]) -> dict:
    """Mean score for one competency across the answers that tested it."""
    scored = [answer for answer in answers if answer.get("score") is not None]

    scores = [answer["score"] for answer in scored]

    mean = round(sum(scores) / len(scores), 2) if scores else None

    return {
        "competency": competency,
        "name": entry.get("name", competency),
        "weight": entry.get("weight", 0),
        "score": mean,
        "percent": to_percent(mean),
        "answers_scored": len(scored),
        "answers_total": len(answers),
        "evidence": [
            {
                "question_id": answer.get("question_id"),
                "score": answer.get("score"),
                "quote": answer.get("evidence_quote", ""),
                "quote_verified": answer.get("quote_verified", False),
                "reasoning": answer.get("reasoning", ""),
            }
            for answer in answers
        ],
        "flags": sorted(
            {flag for answer in answers for flag in answer.get("flags") or []}
        ),
    }


def weighted_overall(competency_scores: list[dict]) -> tuple[float | None, dict]:
    """Weighted mean over the competencies that produced a score.

    Competencies with no score are excluded and their weight is redistributed
    across the rest, so one unscoreable answer lowers confidence rather than
    silently dragging the overall score towards zero.
    """
    scored = [entry for entry in competency_scores if entry["score"] is not None]

    if not scored:
        return None, {
            "method": "weighted_mean",
            "competencies_used": 0,
            "competencies_total": len(competency_scores),
            "weights": {},
            "note": "No competency produced a score.",
        }

    total_weight = sum(entry["weight"] for entry in scored)

    if total_weight <= 0:
        # Weights all zero: fall back to an unweighted mean rather than fail.
        overall = sum(entry["score"] for entry in scored) / len(scored)

        used_weights = {
            entry["competency"]: round(1 / len(scored), 4) for entry in scored
        }
    else:
        overall = (
            sum(entry["score"] * entry["weight"] for entry in scored) / total_weight
        )

        used_weights = {
            entry["competency"]: round(entry["weight"] / total_weight, 4)
            for entry in scored
        }

    excluded = [
        entry["competency"]
        for entry in competency_scores
        if entry["score"] is None
    ]

    workings = {
        "method": "weighted_mean",
        "competencies_used": len(scored),
        "competencies_total": len(competency_scores),
        "weights": used_weights,
        "excluded": excluded,
        "note": (
            "Overall is the weighted mean of the competency scores shown, "
            "using the weights listed here (rescaled to sum to 1 over the "
            "competencies that produced a score)."
        ),
    }

    return round(overall, 2), workings


def build_scorecard(
    session: dict,
    rubric: list[dict],
    answer_scores: list[dict],
) -> dict:
    """Assemble per-competency and overall scores, with evidence and flags.

    `answer_scores` is one entry per question of the session - including
    questions with no answer, which are reported as unanswered rather than
    omitted, so a scorecard always covers the whole interview.
    """
    rubric_entries = {entry["competency"]: entry for entry in rubric}

    by_competency: dict[str, list[dict]] = {}

    for answer in answer_scores:
        by_competency.setdefault(answer["competency"], []).append(answer)

    competency_scores = [
        aggregate_competency(
            competency,
            rubric_entries.get(competency, {"name": competency, "weight": 0}),
            answers,
        )
        for competency, answers in by_competency.items()
    ]

    # Report in rubric order so two scorecards read the same way.
    order = {entry["competency"]: index for index, entry in enumerate(rubric)}

    competency_scores.sort(key=lambda entry: order.get(entry["competency"], 99))

    overall, workings = weighted_overall(competency_scores)

    review_items = [
        {
            "question_id": answer.get("question_id"),
            "competency": answer["competency"],
            "flags": [
                flag for flag in answer.get("flags") or [] if flag in REVIEW_FLAGS
            ],
        }
        for answer in answer_scores
        if any(flag in REVIEW_FLAGS for flag in answer.get("flags") or [])
    ]

    all_flags = sorted(
        {flag for answer in answer_scores for flag in answer.get("flags") or []}
    )

    scored_count = sum(
        1 for answer in answer_scores if answer.get("score") is not None
    )

    return {
        "overall_score": overall,
        "overall_percent": to_percent(overall),
        "scale": {"min": SCORE_MIN, "max": SCORE_MAX},
        "questions_total": len(answer_scores),
        "answers_scored": scored_count,
        "competency_scores": competency_scores,
        "weighting": workings,
        "flags": all_flags,
        "needs_human_review": bool(review_items) or scored_count == 0,
        "review_items": review_items,
        "rubric": [
            {
                "competency": entry["competency"],
                "name": entry["name"],
                "weight": entry["weight"],
                "descriptors": {
                    str(level): text
                    for level, text in entry["descriptors"].items()
                },
            }
            for entry in rubric
        ],
    }

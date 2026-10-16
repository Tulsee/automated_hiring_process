"""The fixed, ordered interview template.

Questions are fixed per job rather than generated per candidate: every
candidate for a job answers the same questions in the same order, which is what
makes the later per-competency scoring comparable between candidates.

Each question carries the competency it tests, so Sprint 5 can score answers
against a rubric per competency instead of one undifferentiated score.
"""

import logging

logger = logging.getLogger(__name__)

# Competencies the template scores against.
COMPETENCY_TECHNICAL_DEPTH = "technical_depth"
COMPETENCY_SYSTEM_DESIGN = "system_design"
COMPETENCY_PROBLEM_SOLVING = "problem_solving"

DEFAULT_INTERVIEW_QUESTIONS = [
    {
        "id": "question_1",
        "text": "Tell us about your backend development experience.",
        "competency": COMPETENCY_TECHNICAL_DEPTH,
        "time_limit_seconds": 60,
    },
    {
        "id": "question_2",
        "text": "How would you design a scalable REST API?",
        "competency": COMPETENCY_SYSTEM_DESIGN,
        "time_limit_seconds": 90,
    },
    {
        "id": "question_3",
        "text": "Describe a challenging technical problem you solved.",
        "competency": COMPETENCY_PROBLEM_SOLVING,
        "time_limit_seconds": 120,
    },
]

DEFAULT_TIME_LIMIT_SECONDS = 90


def normalise_question(question: dict, index: int) -> dict:
    """Fill in anything a job-defined question left out."""
    return {
        "id": question.get("id") or f"question_{index + 1}",
        "text": question["text"],
        "competency": question.get("competency") or "general",
        "time_limit_seconds": int(
            question.get("time_limit_seconds") or DEFAULT_TIME_LIMIT_SECONDS
        ),
    }


def get_questions_for_job(job: dict | None) -> list[dict]:
    """The ordered questions for a job, falling back to the default template.

    A job may define its own `interview_questions`; jobs created before that
    field existed simply use the default set.
    """
    questions = (job or {}).get("interview_questions")

    if not questions:
        logger.info("Job has no interview questions; using the default template")
        return [dict(question) for question in DEFAULT_INTERVIEW_QUESTIONS]

    return [
        normalise_question(question, index)
        for index, question in enumerate(questions)
    ]

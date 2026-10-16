"""Module 15: score one interview answer against the rubric.

The model returns `{competency, score, evidence_quote, reasoning}` and every
score must be backed by a quote from the transcript. That quote is then
*verified* against the transcript rather than trusted: an LLM asked for
evidence will paraphrase or invent one, and an unverifiable quote means the
score behind it cannot be defended, so it is flagged for a human.
"""

import json
import logging
import re

from ollama import AsyncClient

from app.core.config import settings
from app.services.rubric import (
    SCORE_MAX,
    SCORE_MIN,
    entry_for_competency,
    format_descriptors,
)

logger = logging.getLogger(__name__)

SCORE_FLAG_EMPTY = "empty_answer"
SCORE_FLAG_TOO_SHORT = "answer_too_short"
SCORE_FLAG_OFF_TOPIC = "off_topic"
SCORE_FLAG_UNVERIFIED_QUOTE = "unverified_quote"
SCORE_FLAG_NO_QUOTE = "no_evidence_quote"
SCORE_FLAG_SCORING_FAILED = "scoring_failed"

# Below this the answer has too little content to score fairly.
MIN_SCOREABLE_WORDS = 8

SYSTEM_PROMPT = """
You are an interview scoring system. You score ONE answer against ONE
competency on a 1-5 scale, using only the rubric you are given.

Return ONLY valid JSON in exactly this structure:

{
    "competency": "string",
    "score": 1,
    "evidence_quote": "string",
    "reasoning": "string",
    "answers_question": true
}

Rules:

1. The score must be an integer from 1 to 5, matching the rubric descriptors.
2. "evidence_quote" MUST be copied word-for-word from the transcript. Do not
   paraphrase, correct, summarise or shorten it. Copy a contiguous span of the
   candidate's own words.
3. If the transcript contains nothing that supports a score, use an empty
   string for "evidence_quote" and score 1.
4. "reasoning" must be one sentence explaining the score by reference to the
   rubric.
5. "answers_question" is false when the answer is off-topic - it does not
   address the question that was asked.
6. Judge only what the candidate says. Ignore grammar, accent, fluency and
   transcription errors.
7. Do not reward length. A short, specific answer can score 5.
"""

USER_PROMPT = """\
QUESTION ASKED:
{question_text}

COMPETENCY BEING SCORED: {competency_name} ({competency})
{competency_description}

RUBRIC (1-5):
{descriptors}

CANDIDATE'S ANSWER (transcript):
\"\"\"
{transcript}
\"\"\"

Score this answer for {competency_name} only.
"""


def normalise_for_matching(text: str) -> str:
    """Lowercase, strip punctuation and collapse whitespace.

    Transcripts carry commas and casing the model tends to "tidy up", so an
    exact string match rejects quotes that are really present. This compares
    the words alone.
    """
    return re.sub(r"[^a-z0-9 ]", " ", text.lower()).strip()


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def verify_quote(quote: str, transcript: str) -> bool:
    """Is this quote actually in the transcript?

    Allows for punctuation and casing differences, but not for invented or
    reordered content.
    """
    if not quote or not quote.strip():
        return False

    normalised_quote = collapse_whitespace(normalise_for_matching(quote))

    normalised_transcript = collapse_whitespace(normalise_for_matching(transcript))

    if not normalised_quote:
        return False

    return normalised_quote in normalised_transcript


def clamp_score(value) -> int | None:
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        return None

    return max(SCORE_MIN, min(SCORE_MAX, score))


def unscoreable(transcript: str, competency: str, flags: list[str]) -> dict:
    """The result for an answer there is no point sending to the model."""
    return {
        "competency": competency,
        "score": None,
        "evidence_quote": "",
        "quote_verified": False,
        "reasoning": (
            "Not scored: the answer has too little content to judge."
            if transcript.strip()
            else "Not scored: no answer was recorded."
        ),
        "answers_question": False,
        "flags": flags,
        "model": None,
    }


async def score_answer(
    transcript: str,
    question: dict,
    rubric: list[dict],
    client: AsyncClient | None = None,
) -> dict:
    """Score one transcript against the question's competency.

    Returns the rubric result plus `quote_verified` and `flags`. Never raises
    for a bad answer or a bad model response - it reports the problem as a
    flag so one answer cannot abandon a whole scorecard.
    """
    transcript = transcript or ""

    entry = entry_for_competency(rubric, question.get("competency"))

    competency = entry["competency"]

    word_count = len(transcript.split())

    # Don't spend a model call on an answer that cannot be scored fairly.
    if word_count == 0:
        return unscoreable(transcript, competency, [SCORE_FLAG_EMPTY])

    if word_count < MIN_SCOREABLE_WORDS:
        return unscoreable(transcript, competency, [SCORE_FLAG_TOO_SHORT])

    client = client or AsyncClient()

    prompt = USER_PROMPT.format(
        question_text=question.get("text", "(question text unavailable)"),
        competency_name=entry["name"],
        competency=competency,
        competency_description=entry.get("description", ""),
        descriptors=format_descriptors(entry),
        transcript=transcript,
    )

    try:
        response = await client.chat(
            model=settings.SCORING_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            format="json",
            think=False,
        )

        data = json.loads(response["message"]["content"])

    except Exception as error:
        logger.error(
            "Scoring failed for competency %s: %s", competency, error
        )

        return {
            "competency": competency,
            "score": None,
            "evidence_quote": "",
            "quote_verified": False,
            "reasoning": f"Scoring failed: {error}",
            "answers_question": None,
            "flags": [SCORE_FLAG_SCORING_FAILED],
            "model": settings.SCORING_MODEL,
        }

    score = clamp_score(data.get("score"))

    quote = (data.get("evidence_quote") or "").strip()

    quote_verified = verify_quote(quote, transcript)

    flags = []

    if not quote:
        flags.append(SCORE_FLAG_NO_QUOTE)
    elif not quote_verified:
        # The model produced a quote that is not in the transcript, so the
        # score behind it is not evidence-backed.
        logger.warning(
            "Unverified evidence quote for %s: %r", competency, quote[:120]
        )

        flags.append(SCORE_FLAG_UNVERIFIED_QUOTE)

    if data.get("answers_question") is False:
        flags.append(SCORE_FLAG_OFF_TOPIC)

    if score is None:
        flags.append(SCORE_FLAG_SCORING_FAILED)

    return {
        "competency": competency,
        "score": score,
        "evidence_quote": quote,
        "quote_verified": quote_verified,
        "reasoning": (data.get("reasoning") or "").strip(),
        "answers_question": data.get("answers_question"),
        "flags": flags,
        "model": settings.SCORING_MODEL,
    }

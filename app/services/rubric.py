"""The scoring rubric: 1-5 descriptors per job-related competency.

A rubric, not a clever prompt, is what makes scoring consistent. Each
competency names what it measures, carries an explicit weight, and spells out
what a 1, 3 and 5 look like, so two different answers get judged against the
same written standard and a score can be argued with.

Every competency here must be tied to the job. The plan's rule of thumb: if you
cannot explain a score in one sentence backed by a quote, drop the competency.
"""

import logging

logger = logging.getLogger(__name__)

# A rubric with one or two competencies says little; more than five and the
# weights stop meaning anything.
MIN_COMPETENCIES = 3
MAX_COMPETENCIES = 5

SCORE_MIN = 1
SCORE_MAX = 5

DEFAULT_RUBRIC = [
    {
        "competency": "technical_depth",
        "name": "Technical depth",
        "description": (
            "Concrete, first-hand knowledge of the tools and techniques the "
            "role uses, with specifics rather than labels."
        ),
        "weight": 0.35,
        "descriptors": {
            1: (
                "Names technologies without showing use; no specifics, or "
                "describes them incorrectly."
            ),
            3: (
                "Describes real hands-on work with the relevant stack; some "
                "detail, but stays mostly at surface level."
            ),
            5: (
                "Explains specific work in depth, including why choices were "
                "made and what the limitations were."
            ),
        },
    },
    {
        "competency": "system_design",
        "name": "System design",
        "description": (
            "Ability to shape a system to meet a requirement, and to reason "
            "about scale, failure and trade-offs."
        ),
        "weight": 0.35,
        "descriptors": {
            1: (
                "No structure; lists components with no reasoning about how "
                "they fit together."
            ),
            3: (
                "A workable design addressing the core requirement, with "
                "gaps around scale or failure."
            ),
            5: (
                "A clear design that names trade-offs, bottlenecks and "
                "failure modes, and justifies the choices made."
            ),
        },
    },
    {
        "competency": "problem_solving",
        "name": "Problem-solving approach",
        "description": (
            "How the candidate frames an unfamiliar problem, works towards a "
            "solution, and verifies it."
        ),
        "weight": 0.30,
        "descriptors": {
            1: (
                "No structured approach; misses what the problem actually "
                "is."
            ),
            3: (
                "A reasonable approach that addresses the core problem, with "
                "some gaps in reasoning."
            ),
            5: (
                "Clear, structured reasoning that considers trade-offs and "
                "edge cases, and says how the result was checked."
            ),
        },
    },
]

# Any competency a question declares but the rubric does not define falls back
# to this, so a job-specific question can never silently go unscored.
GENERAL_COMPETENCY = {
    "competency": "general",
    "name": "General response quality",
    "description": (
        "Whether the answer actually addresses the question asked, with "
        "relevant and specific content."
    ),
    "weight": 0.20,
    "descriptors": {
        1: "Does not address the question, or says nothing substantive.",
        3: "Addresses the question with some relevant specifics.",
        5: "Answers the question directly, in depth, with concrete detail.",
    },
}


class RubricError(ValueError):
    """The rubric is not usable as written."""


def normalise_entry(entry: dict, index: int) -> dict:
    """Fill in anything a job-defined rubric entry left out."""
    competency = entry.get("competency") or entry.get("name")

    if not competency:
        raise RubricError(f"Rubric entry {index} has no competency")

    descriptors = entry.get("descriptors") or {}

    # JSON object keys arrive as strings; the rest of the code wants ints.
    try:
        descriptors = {int(level): text for level, text in descriptors.items()}
    except (TypeError, ValueError) as error:
        raise RubricError(
            f"Competency '{competency}' has a non-numeric descriptor level: "
            f"{error}"
        ) from error

    out_of_range = [
        level for level in descriptors if not SCORE_MIN <= level <= SCORE_MAX
    ]

    if out_of_range:
        raise RubricError(
            f"Competency '{competency}' has descriptor levels outside "
            f"{SCORE_MIN}-{SCORE_MAX}: {sorted(out_of_range)}"
        )

    if not descriptors:
        raise RubricError(
            f"Competency '{competency}' has no descriptors; a score with no "
            "written standard behind it cannot be defended"
        )

    return {
        "competency": competency,
        "name": entry.get("name") or competency.replace("_", " ").capitalize(),
        "description": entry.get("description") or "",
        "weight": float(entry.get("weight") or 0),
        "descriptors": descriptors,
    }


def validate_rubric(rubric: list[dict]) -> list[dict]:
    """Check a rubric is scoreable, and normalise its weights to sum to 1."""
    if not rubric:
        raise RubricError("The rubric is empty")

    if not MIN_COMPETENCIES <= len(rubric) <= MAX_COMPETENCIES:
        raise RubricError(
            f"A rubric needs {MIN_COMPETENCIES}-{MAX_COMPETENCIES} "
            f"competencies, got {len(rubric)}"
        )

    entries = [normalise_entry(entry, index) for index, entry in enumerate(rubric)]

    competencies = [entry["competency"] for entry in entries]

    duplicates = {name for name in competencies if competencies.count(name) > 1}

    if duplicates:
        raise RubricError(f"Duplicate competencies in the rubric: {duplicates}")

    total_weight = sum(entry["weight"] for entry in entries)

    if total_weight <= 0:
        # No weights given: weight every competency equally.
        for entry in entries:
            entry["weight"] = round(1 / len(entries), 4)
    elif abs(total_weight - 1.0) > 0.001:
        # Rescale rather than reject, so weights can be written as 2/3/5.
        logger.info("Rubric weights sum to %.3f; rescaling to 1.0", total_weight)

        for entry in entries:
            entry["weight"] = round(entry["weight"] / total_weight, 4)

    return entries


def get_rubric_for_job(job: dict | None) -> list[dict]:
    """The rubric for a job, falling back to the default competencies."""
    rubric = (job or {}).get("interview_rubric")

    if not rubric:
        return validate_rubric([dict(entry) for entry in DEFAULT_RUBRIC])

    return validate_rubric(rubric)


def rubric_by_competency(rubric: list[dict]) -> dict[str, dict]:
    return {entry["competency"]: entry for entry in rubric}


def entry_for_competency(rubric: list[dict], competency: str | None) -> dict:
    """The rubric row to score a question against.

    A question whose competency the rubric does not define still gets scored,
    against the general row, rather than being dropped.
    """
    if competency:
        entry = rubric_by_competency(rubric).get(competency)

        if entry:
            return entry

        logger.warning(
            "Competency '%s' is not in the rubric; scoring it as general",
            competency,
        )

    return dict(GENERAL_COMPETENCY)


def format_descriptors(entry: dict) -> str:
    """The rubric row as the scale shown to the model."""
    return "\n".join(
        f"  {level} - {entry['descriptors'][level]}"
        for level in sorted(entry["descriptors"])
    )

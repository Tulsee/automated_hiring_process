"""The stages an application passes through, for the candidate's own view.

A candidate wants to know where their application is and what is left. The
pipeline already records everything needed to answer that - the candidate's
status and decision, and the interview session's status - so the journey is
*derived* from those rather than stored as a separate field that could drift.

The stages, in order:

    applied     -> the resume was received
    screening   -> the AI score is being / has been computed
    decision    -> the recruiter's screen decision (invite or not)
    interview   -> only if invited: record the video answers
    assessment  -> the interview is transcribed and scored
    outcome     -> a person makes the final call

A stage is `done`, `current`, `pending`, or `skipped` (e.g. the interview
stages when an application was not progressed past screening).
"""

DONE = "done"
CURRENT = "current"
PENDING = "pending"
SKIPPED = "skipped"

# The decisions that mean "not progressed".
REJECTED_DECISIONS = {"reject", "rejected"}
INVITED_DECISIONS = {"invited_to_interview", "invite_to_interview"}


def _step(key: str, title: str, state: str, detail: str) -> dict:
    return {"key": key, "title": title, "state": state, "detail": detail}


def application_journey(candidate: dict, session: dict | None = None) -> list[dict]:
    """The ordered steps for one application, each with its state and a note."""
    status = candidate.get("status", "received")
    decision = candidate.get("decision")
    rejected = decision in REJECTED_DECISIONS
    invited = decision in INVITED_DECISIONS

    # A decision can only have been made after screening, so a decided
    # application has screened even if the stored score is absent.
    scored = candidate.get("screening_score") is not None or bool(decision)
    errored = status == "error"

    steps: list[dict] = []

    # 1. Applied - always done once the record exists.
    steps.append(
        _step("applied", "Applied", DONE, "Your application was received.")
    )

    # 2. Screening.
    if errored:
        steps.append(
            _step(
                "screening",
                "Screening",
                CURRENT,
                "We could not read your resume automatically; the team will "
                "review it by hand.",
            )
        )
    elif scored:
        steps.append(
            _step(
                "screening",
                "Screening",
                DONE,
                "Your resume has been assessed against the role.",
            )
        )
    else:
        steps.append(
            _step(
                "screening",
                "Screening",
                CURRENT,
                "Your resume is being assessed against the role.",
            )
        )

    # 3. Decision on the screen.
    if rejected:
        steps.append(
            _step(
                "decision",
                "Screening decision",
                DONE,
                "After review, you were not progressed for this role.",
            )
        )
    elif invited:
        steps.append(
            _step(
                "decision",
                "Screening decision",
                DONE,
                "You were invited to the interview stage.",
            )
        )
    else:
        steps.append(
            _step(
                "decision",
                "Screening decision",
                PENDING if scored else PENDING,
                "A recruiter will decide whether to invite you to interview.",
            )
        )

    # 4 & 5. Interview and assessment - only on the invited path.
    if rejected:
        steps.append(
            _step("interview", "Interview", SKIPPED, "Not part of your path.")
        )
        steps.append(
            _step("assessment", "Assessment", SKIPPED, "Not part of your path.")
        )
    else:
        session_status = (session or {}).get("status")
        answered = (session or {}).get("answered_count", 0)
        total = (session or {}).get("total_questions", 0)

        if session_status == "submitted":
            steps.append(
                _step("interview", "Interview", DONE, "Your answers are recorded.")
            )
        elif session_status == "in_progress":
            steps.append(
                _step(
                    "interview",
                    "Interview",
                    CURRENT,
                    f"Record your video answers ({answered} of {total} done)."
                    if total
                    else "Record your video answers from your invite link.",
                )
            )
        elif session_status == "invited" or invited:
            steps.append(
                _step(
                    "interview",
                    "Interview",
                    CURRENT,
                    "Open your interview invite link to record your answers.",
                )
            )
        else:
            steps.append(
                _step(
                    "interview",
                    "Interview",
                    PENDING,
                    "If you are invited, you will record video answers.",
                )
            )

        scoring_status = (session or {}).get("scoring_status")

        if scoring_status == "completed":
            assessment_state, assessment_detail = (
                DONE,
                "Your interview has been assessed.",
            )
        elif session_status == "submitted":
            assessment_state, assessment_detail = (
                CURRENT,
                "Your interview is being assessed.",
            )
        else:
            assessment_state, assessment_detail = (
                PENDING,
                "Your interview answers will be assessed.",
            )

        steps.append(
            _step("assessment", "Assessment", assessment_state, assessment_detail)
        )

    # 6. Outcome - the final human call. A recorded final decision (or a
    # screening rejection) completes it; otherwise it waits on a person.
    final_decision = candidate.get("final_decision")

    if final_decision == "hired":
        steps.append(
            _step("outcome", "Outcome", DONE, "You have been selected - an offer is on its way.")
        )
    elif final_decision == "next_round":
        steps.append(
            _step("outcome", "Outcome", CURRENT, "You are moving to a further interview round.")
        )
    elif final_decision == "rejected":
        steps.append(
            _step("outcome", "Outcome", DONE, "After review, you were not progressed for this role.")
        )
    elif rejected:
        steps.append(
            _step("outcome", "Outcome", DONE, "A decision has been made.")
        )
    else:
        steps.append(
            _step(
                "outcome",
                "Outcome",
                PENDING,
                "A person makes the final decision after review.",
            )
        )

    return steps


def current_stage(steps: list[dict]) -> dict:
    """The step a candidate is waiting on - the first not-done, non-skipped one.

    Falls back to the last step when everything is done, so there is always a
    sensible 'where you are' to show.
    """
    for step in steps:
        if step["state"] in {CURRENT, PENDING}:
            return step

    return steps[-1]


def journey_summary(candidate: dict, session: dict | None = None) -> dict:
    steps = application_journey(candidate, session)

    done = sum(1 for step in steps if step["state"] == DONE)
    relevant = [step for step in steps if step["state"] != SKIPPED]

    return {
        "steps": steps,
        "current": current_stage(steps),
        "completed": done,
        "total": len(relevant),
    }

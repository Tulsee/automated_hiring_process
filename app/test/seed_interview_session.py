"""Manual helper: create an interview-eligible candidate and an invite.

Run it, then open the invite URL it prints to record the interview in a
browser. Pass the port your API is on (default 8010):

    uv run python app/test/seed_interview_session.py 8010

Pass `--default-questions` to seed a job with no questions of its own, so the
default template is used instead of a job-specific one.
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.mongodb import candidates_collection, jobs_collection
from app.services.interview_service import (
    DECISION_INVITED_TO_INTERVIEW,
    create_session_for_candidate,
)

ARGS = [arg for arg in sys.argv[1:] if not arg.startswith("--")]

PORT = ARGS[0] if ARGS else "8010"
BASE_URL = f"http://127.0.0.1:{PORT}"

USE_DEFAULT_QUESTIONS = "--default-questions" in sys.argv

# A job-specific template, each question tagged with the competency it tests.
JOB_INTERVIEW_QUESTIONS = [
    {
        "id": "backend_experience",
        "text": "Tell us about your backend development experience.",
        "competency": "technical_depth",
        "time_limit_seconds": 60,
    },
    {
        "id": "api_design",
        "text": "How would you design a scalable REST API?",
        "competency": "system_design",
        "time_limit_seconds": 90,
    },
    {
        "id": "hard_problem",
        "text": "Describe a challenging technical problem you solved.",
        "competency": "problem_solving",
        "time_limit_seconds": 120,
    },
]


async def main():
    job_result = await jobs_collection.insert_one(
        {
            "title": "Backend Engineer",
            "description": "Seeded by seed_interview_session.py",
            "required_skills": ["python", "fastapi", "mongodb"],
            "minimum_experience": 2,
            "interview_questions": (
                [] if USE_DEFAULT_QUESTIONS else JOB_INTERVIEW_QUESTIONS
            ),
        }
    )

    job_id = str(job_result.inserted_id)

    candidate_result = await candidates_collection.insert_one(
        {
            "job_id": job_id,
            "name": "Test Candidate",
            "email": "test.candidate@example.com",
            "status": "screened",
            "decision": DECISION_INVITED_TO_INTERVIEW,
        }
    )

    candidate = await candidates_collection.find_one(
        {"_id": candidate_result.inserted_id}
    )

    # The same service the API route and the screening graph use.
    created = await create_session_for_candidate(candidate)

    print("\n========== SEEDED ==========\n")
    print(f"job_id       : {job_id}")
    print(f"candidate_id : {str(candidate['_id'])}")
    print(f"session_id   : {created['session_id']}")
    print(
        "questions    : "
        f"{len(created['questions'])}"
        f" ({'default template' if USE_DEFAULT_QUESTIONS else 'job template'})"
    )

    for question in created["questions"]:
        print(
            f"               - {question['id']}"
            f"  [{question['competency']}]"
            f"  {question['time_limit_seconds']}s"
        )

    print(f"expires_at   : {created['session']['invite_expires_at']} UTC")
    print("\n>>> OPEN THIS IN YOUR BROWSER <<<\n")
    print(f"  {BASE_URL}/interview?token={created['invite_token']}")
    print("\n============================\n")


if __name__ == "__main__":
    asyncio.run(main())

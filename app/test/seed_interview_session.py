"""Manual helper: create an interview-eligible candidate and a session.

Run it, then open the URL it prints to record the interview in a browser.

    uv run python app/test/seed_interview_session.py
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from bson import ObjectId

from app.db.mongodb import (
    candidates_collection,
    interview_sessions_collection,
    jobs_collection,
)


PORT = sys.argv[1] if len(sys.argv) > 1 else "8010"
BASE_URL = f"http://127.0.0.1:{PORT}"


async def main():
    job_result = await jobs_collection.insert_one(
        {
            "title": "Backend Engineer",
            "description": "Seeded by seed_interview_session.py",
            "required_skills": ["python", "fastapi", "mongodb"],
        }
    )

    job_id = str(job_result.inserted_id)

    candidate_result = await candidates_collection.insert_one(
        {
            "job_id": job_id,
            "name": "Test Candidate",
            "email": "test.candidate@example.com",
            "status": "screened",
            "decision": "invited_to_interview",
        }
    )

    candidate_id = str(candidate_result.inserted_id)

    print("\n========== SEEDED ==========\n")
    print(f"job_id       : {job_id}")
    print(f"candidate_id : {candidate_id}")
    print("\nCreate the session:\n")
    print(
        "  curl -X POST http://127.0.0.1:8000/interviews/sessions \\\n"
        '    -H "Content-Type: application/json" \\\n'
        f'    -d \'{{"candidate_id": "{candidate_id}"}}\''
    )
    print("\nOr let this script do it too (it already did):\n")

    # Create the session through the same route logic the API uses.
    from app.models.interview_session import create_interview_session_document

    questions = [
        {
            "id": "question_1",
            "text": "Tell us about your backend development experience.",
            "time_limit_seconds": 60,
        },
        {
            "id": "question_2",
            "text": "How would you design a scalable REST API?",
            "time_limit_seconds": 90,
        },
        {
            "id": "question_3",
            "text": "Describe a challenging technical problem you solved.",
            "time_limit_seconds": 120,
        },
    ]

    session = create_interview_session_document(
        candidate_id=candidate_id,
        job_id=job_id,
        questions=questions,
    )

    session_result = await interview_sessions_collection.insert_one(session)

    session_id = str(session_result.inserted_id)

    print(f"session_id   : {session_id}")
    print(f"questions    : {len(questions)}")
    print("\n>>> OPEN THIS IN YOUR BROWSER <<<\n")
    print(f"  {BASE_URL}/interview?session_id={session_id}")
    print("\n============================\n")


if __name__ == "__main__":
    asyncio.run(main())

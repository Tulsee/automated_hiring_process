"""Tests for listing candidates and reading one candidate's detail.

Without these, a candidate_id could only be found by reading the database
directly - the screening and vector endpoints both require one.
"""

from datetime import datetime, timedelta

import pytest
from bson import ObjectId


def add_job(fakes, title="Backend Engineer"):
    job = {"_id": ObjectId(), "title": title, "required_skills": ["python"]}
    fakes.jobs.documents.append(job)
    return job


def add_candidate(
    fakes,
    job_id,
    *,
    name="Candidate",
    score=None,
    status="received",
    decision=None,
    created_at=None,
    skills=None,
    **extra,
):
    candidate = {
        "_id": ObjectId(),
        "job_id": str(job_id),
        "name": name,
        "email": f"{name.lower().replace(' ', '.')}@example.com",
        "status": status,
        "decision": decision,
        "screening_score": score,
        "skills": skills if skills is not None else ["python", "fastapi"],
        "resume_filename": f"{name}.pdf",
        "created_at": created_at or datetime.utcnow(),
        **extra,
    }
    fakes.candidates.documents.append(candidate)
    return candidate


class TestListAllCandidates:
    async def test_lists_every_candidate(self, client, fakes):
        job = add_job(fakes)
        add_candidate(fakes, job["_id"], name="Ama")
        add_candidate(fakes, job["_id"], name="Bo")

        response = await client.get("/applications/")

        assert response.status_code == 200
        body = response.json()

        assert body["total"] == 2
        assert body["count"] == 2
        assert {c["name"] for c in body["candidates"]} == {"Ama", "Bo"}

    async def test_an_empty_system_returns_an_empty_list(self, client, fakes):
        response = await client.get("/applications/")

        assert response.status_code == 200
        assert response.json()["total"] == 0
        assert response.json()["candidates"] == []

    async def test_a_summary_row_carries_what_you_need_to_scan(
        self, client, fakes
    ):
        job = add_job(fakes)
        candidate = add_candidate(
            fakes,
            job["_id"],
            name="Ama",
            score=82.5,
            status="screened",
            decision="invited_to_interview",
            years_of_experience=6,
            skills=["python", "fastapi", "mongodb"],
        )

        row = (await client.get("/applications/")).json()["candidates"][0]

        assert row["id"] == str(candidate["_id"])
        assert row["job_id"] == str(job["_id"])
        assert row["name"] == "Ama"
        assert row["email"] == "ama@example.com"
        assert row["status"] == "screened"
        assert row["decision"] == "invited_to_interview"
        assert row["screening_score"] == 82.5
        assert row["years_of_experience"] == 6
        assert row["skills_count"] == 3
        assert row["resume_filename"] == "Ama.pdf"

    async def test_the_id_can_be_used_on_the_screening_endpoint(
        self, client, fakes
    ):
        """The point of the listing: discovering a usable candidate_id."""
        job = add_job(fakes)
        add_candidate(fakes, job["_id"], score=77.0)

        listed_id = (await client.get("/applications/")).json()["candidates"][0][
            "id"
        ]

        response = await client.get(f"/applications/{listed_id}/screening")

        assert response.status_code == 200
        assert response.json()["screening_score"] == 77.0


class TestListByJob:
    async def test_only_candidates_for_that_job(self, client, fakes):
        backend = add_job(fakes, "Backend Engineer")
        design = add_job(fakes, "Designer")

        add_candidate(fakes, backend["_id"], name="Ama")
        add_candidate(fakes, backend["_id"], name="Bo")
        add_candidate(fakes, design["_id"], name="Cem")

        body = (
            await client.get(f"/applications/?job_id={backend['_id']}")
        ).json()

        assert body["total"] == 2
        assert body["job_id"] == str(backend["_id"])
        assert body["job_title"] == "Backend Engineer"
        assert {c["name"] for c in body["candidates"]} == {"Ama", "Bo"}

    async def test_a_job_with_no_applicants_is_empty_not_an_error(
        self, client, fakes
    ):
        job = add_job(fakes)

        body = (await client.get(f"/applications/?job_id={job['_id']}")).json()

        assert body["total"] == 0
        assert body["candidates"] == []

    async def test_an_unknown_job_is_rejected(self, client, fakes):
        response = await client.get(f"/applications/?job_id={ObjectId()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Job not found"

    async def test_a_malformed_job_id_is_rejected(self, client):
        response = await client.get("/applications/?job_id=nope")

        assert response.status_code == 400


class TestSortingAndFiltering:
    async def test_highest_scoring_first_by_default(self, client, fakes):
        job = add_job(fakes)
        add_candidate(fakes, job["_id"], name="Low", score=40.0)
        add_candidate(fakes, job["_id"], name="High", score=90.0)
        add_candidate(fakes, job["_id"], name="Mid", score=65.0)

        body = (await client.get("/applications/")).json()

        assert [c["name"] for c in body["candidates"]] == ["High", "Mid", "Low"]

    async def test_unscored_candidates_sort_last(self, client, fakes):
        """Still-processing candidates must not crowd out ranked ones."""
        job = add_job(fakes)
        add_candidate(fakes, job["_id"], name="Pending", score=None)
        add_candidate(fakes, job["_id"], name="Scored", score=50.0)

        body = (await client.get("/applications/")).json()

        assert [c["name"] for c in body["candidates"]] == ["Scored", "Pending"]

    async def test_sort_by_most_recent(self, client, fakes):
        job = add_job(fakes)
        now = datetime.utcnow()

        add_candidate(
            fakes, job["_id"], name="Older", created_at=now - timedelta(days=2)
        )
        add_candidate(fakes, job["_id"], name="Newer", created_at=now)

        body = (await client.get("/applications/?sort=recent")).json()

        assert [c["name"] for c in body["candidates"]] == ["Newer", "Older"]

    async def test_sort_by_name(self, client, fakes):
        job = add_job(fakes)
        add_candidate(fakes, job["_id"], name="Zoe")
        add_candidate(fakes, job["_id"], name="Ada")

        body = (await client.get("/applications/?sort=name")).json()

        assert [c["name"] for c in body["candidates"]] == ["Ada", "Zoe"]

    async def test_an_unknown_sort_is_rejected(self, client):
        response = await client.get("/applications/?sort=sideways")

        assert response.status_code == 422

    async def test_filter_by_status(self, client, fakes):
        job = add_job(fakes)
        add_candidate(fakes, job["_id"], name="New", status="received")
        add_candidate(fakes, job["_id"], name="Done", status="screened")

        body = (await client.get("/applications/?status=screened")).json()

        assert body["total"] == 1
        assert body["candidates"][0]["name"] == "Done"

    async def test_filter_by_decision(self, client, fakes):
        job = add_job(fakes)
        add_candidate(fakes, job["_id"], name="In", decision="invited_to_interview")
        add_candidate(fakes, job["_id"], name="Out", decision="reject")

        body = (
            await client.get("/applications/?decision=invited_to_interview")
        ).json()

        assert body["total"] == 1
        assert body["candidates"][0]["name"] == "In"

    async def test_filter_by_minimum_score(self, client, fakes):
        job = add_job(fakes)
        add_candidate(fakes, job["_id"], name="Weak", score=30.0)
        add_candidate(fakes, job["_id"], name="Strong", score=80.0)
        add_candidate(fakes, job["_id"], name="Pending", score=None)

        body = (await client.get("/applications/?min_score=50")).json()

        assert body["total"] == 1
        assert body["candidates"][0]["name"] == "Strong"

    async def test_filters_combine(self, client, fakes):
        backend = add_job(fakes, "Backend")
        other = add_job(fakes, "Other")

        add_candidate(
            fakes, backend["_id"], name="Target", score=75.0, status="screened"
        )
        add_candidate(
            fakes, backend["_id"], name="LowScore", score=20.0, status="screened"
        )
        add_candidate(
            fakes, other["_id"], name="WrongJob", score=99.0, status="screened"
        )

        body = (
            await client.get(
                f"/applications/?job_id={backend['_id']}"
                "&status=screened&min_score=50"
            )
        ).json()

        assert body["total"] == 1
        assert body["candidates"][0]["name"] == "Target"


class TestPagination:
    async def test_limit_and_offset_page_through(self, client, fakes):
        job = add_job(fakes)

        for index in range(5):
            add_candidate(fakes, job["_id"], name=f"C{index}", score=float(index))

        first = (await client.get("/applications/?limit=2")).json()
        second = (await client.get("/applications/?limit=2&offset=2")).json()

        assert first["total"] == 5
        assert first["count"] == 2
        assert [c["name"] for c in first["candidates"]] == ["C4", "C3"]
        assert [c["name"] for c in second["candidates"]] == ["C2", "C1"]

    async def test_total_counts_all_matches_not_just_the_page(
        self, client, fakes
    ):
        job = add_job(fakes)

        for index in range(5):
            add_candidate(fakes, job["_id"], name=f"C{index}")

        body = (await client.get("/applications/?limit=2")).json()

        assert body["total"] == 5
        assert body["count"] == 2

    @pytest.mark.parametrize("query", ["limit=0", "limit=500", "offset=-1"])
    async def test_out_of_range_paging_is_rejected(self, client, query):
        response = await client.get(f"/applications/?{query}")

        assert response.status_code == 422


class TestCandidateDetail:
    async def test_returns_the_full_record(self, client, fakes):
        job = add_job(fakes, "Backend Engineer")
        candidate = add_candidate(
            fakes,
            job["_id"],
            name="Ama",
            score=82.5,
            status="screened",
            decision="invited_to_interview",
            years_of_experience=6,
            education=[{"degree": "BSc", "institution": "X", "year": "2019"}],
            semantic_similarity=0.81,
            skill_score=0.9,
            experience_score=1.0,
            matched_skills=["python", "fastapi"],
            missing_skills=["kubernetes"],
            screening_rationale="Strong API background.",
            decision_message="Passed the bar.",
        )

        response = await client.get(f"/applications/{candidate['_id']}")

        assert response.status_code == 200
        body = response.json()

        assert body["name"] == "Ama"
        assert body["job_title"] == "Backend Engineer"
        assert body["decision"] == "invited_to_interview"
        assert body["years_of_experience"] == 6
        assert body["skills"] == ["python", "fastapi"]
        assert body["education"][0]["degree"] == "BSc"

    async def test_includes_the_screening_breakdown(self, client, fakes):
        job = add_job(fakes)
        candidate = add_candidate(
            fakes,
            job["_id"],
            score=82.5,
            semantic_similarity=0.81,
            skill_score=0.9,
            matched_skills=["python"],
            missing_skills=["go"],
            screening_rationale="Good fit.",
        )

        screening = (
            await client.get(f"/applications/{candidate['_id']}")
        ).json()["screening"]

        assert screening["screening_score"] == 82.5
        assert screening["semantic_similarity"] == 0.81
        assert screening["matched_skills"] == ["python"]
        assert screening["missing_skills"] == ["go"]
        assert screening["rationale"] == "Good fit."

    async def test_includes_interview_progress(self, client, fakes):
        job = add_job(fakes)
        candidate = add_candidate(fakes, job["_id"])
        candidate_id = str(candidate["_id"])

        session = {
            "_id": ObjectId(),
            "candidate_id": candidate_id,
            "job_id": str(job["_id"]),
            "questions": [
                {"id": "q1", "text": "One", "time_limit_seconds": 60},
                {"id": "q2", "text": "Two", "time_limit_seconds": 90},
            ],
            "status": "in_progress",
            "invite_expires_at": datetime.utcnow() + timedelta(hours=10),
            "transcription_status": "pending",
            "submitted_at": None,
        }
        fakes.sessions.documents.append(session)

        fakes.answers.documents.append(
            {
                "_id": ObjectId(),
                "session_id": str(session["_id"]),
                "question_id": "q1",
            }
        )

        interview = (
            await client.get(f"/applications/{candidate_id}")
        ).json()["interview"]

        assert interview["session_id"] == str(session["_id"])
        assert interview["status"] == "in_progress"
        assert interview["total_questions"] == 2
        assert interview["answered_count"] == 1
        assert interview["transcription_status"] == "pending"

    async def test_a_candidate_without_an_interview_has_empty_progress(
        self, client, fakes
    ):
        job = add_job(fakes)
        candidate = add_candidate(fakes, job["_id"])

        interview = (
            await client.get(f"/applications/{candidate['_id']}")
        ).json()["interview"]

        assert interview["session_id"] is None
        assert interview["total_questions"] == 0
        assert interview["answered_count"] == 0

    async def test_an_unprocessed_candidate_still_returns(self, client, fakes):
        """A resume uploaded seconds ago has almost no fields set yet."""
        job = add_job(fakes)

        candidate = {
            "_id": ObjectId(),
            "job_id": str(job["_id"]),
            "resume_filename": "cv.pdf",
            "status": "received",
        }
        fakes.candidates.documents.append(candidate)

        response = await client.get(f"/applications/{candidate['_id']}")

        assert response.status_code == 200
        body = response.json()
        assert body["name"] is None
        assert body["skills"] == []
        assert body["screening"]["screening_score"] is None

    async def test_a_missing_job_does_not_break_the_detail(self, client, fakes):
        candidate = add_candidate(fakes, ObjectId())

        response = await client.get(f"/applications/{candidate['_id']}")

        assert response.status_code == 200
        assert response.json()["job_title"] is None

    async def test_an_unknown_candidate_is_404(self, client, fakes):
        response = await client.get(f"/applications/{ObjectId()}")

        assert response.status_code == 404

    async def test_a_malformed_candidate_id_is_400(self, client):
        response = await client.get("/applications/nope")

        assert response.status_code == 400

    async def test_the_detail_route_does_not_shadow_the_subroutes(
        self, client, fakes
    ):
        """`/{id}` must not swallow `/{id}/screening`."""
        job = add_job(fakes)
        candidate = add_candidate(fakes, job["_id"], score=70.0)

        screening = await client.get(
            f"/applications/{candidate['_id']}/screening"
        )

        assert screening.status_code == 200
        assert screening.json()["screening_score"] == 70.0

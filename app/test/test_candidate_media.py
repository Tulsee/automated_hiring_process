"""Serving a candidate's CV, and notifying a candidate of their outcome."""

from datetime import datetime

from bson import ObjectId

from app.services.decision import apply_decision, FINAL_HIRE


class TestResumeDownload:
    async def test_streams_the_stored_resume(self, client, fakes, tmp_path):
        resume = tmp_path / "cv.pdf"
        resume.write_bytes(b"%PDF-1.4 hello")

        candidate = {
            "_id": ObjectId(),
            "job_id": str(ObjectId()),
            "resume_filename": "cv.pdf",
            "resume_path": str(resume),
        }
        fakes.candidates.documents.append(candidate)

        response = await client.get(f"/applications/{candidate['_id']}/resume")

        assert response.status_code == 200
        assert response.content == b"%PDF-1.4 hello"

    async def test_missing_file_is_404(self, client, fakes):
        candidate = {
            "_id": ObjectId(),
            "job_id": str(ObjectId()),
            "resume_filename": "gone.pdf",
            "resume_path": "/no/such/file.pdf",
        }
        fakes.candidates.documents.append(candidate)

        response = await client.get(f"/applications/{candidate['_id']}/resume")

        assert response.status_code == 404


class TestDecisionNotifiesCandidate:
    async def test_the_candidate_is_notified_of_the_final_decision(self, fakes):
        job = {"_id": ObjectId(), "title": "Backend Engineer"}
        fakes.jobs.documents.append(job)

        user_id = str(ObjectId())
        candidate = {
            "_id": ObjectId(),
            "job_id": str(job["_id"]),
            "name": "Ada",
            "email": "ada@example.com",
            "applicant_user_id": user_id,
        }
        fakes.candidates.documents.append(candidate)

        await apply_decision(str(candidate["_id"]), FINAL_HIRE, reviewer="boss")

        mine = [n for n in fakes.notifications.documents if n["user_id"] == user_id]
        assert len(mine) == 1
        assert "selected" in mine[0]["title"].lower()

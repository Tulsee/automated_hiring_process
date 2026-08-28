import asyncio
from datetime import datetime
from bson import ObjectId
import logging

from app.db.mongodb import candidates_collection, jobs_collection
from app.services.resume_parser import extract_resume_text
from app.services.llm_extractor import extract_candidate_data
from app.services.email_service import send_application_received_email

from app.services.embedding_service import generate_embedding
from app.services.qdrant_service import store_candidate_embedding
from app.services.candidate_screening import (
    screen_candidate,
)

logger = logging.getLogger(__name__)

async def process_candidate(candidate_id: str):
    """
    Background processing pipeline:

    received
       ↓
    processing
       ↓
    extract resume
       ↓
    LLM extraction
       ↓
    processed
    """
    candidate_object_id = ObjectId(candidate_id)

    await candidates_collection.update_one(
        {"_id": candidate_object_id},
        {
            "$set": {
                "status": "processing",
                "updated_at": datetime.utcnow(),
            }
        },
    )

    try:
        candidate = await candidates_collection.find_one({"_id": candidate_object_id})

        if not candidate:
            raise ValueError(f"Candidate with ID {candidate_id} not found.")

        job = await jobs_collection.find_one({"_id": ObjectId(candidate["job_id"])})

        if not job:
            raise ValueError(f"Job with ID {candidate['job_id']} not found.")

        resume_path = candidate["resume_path"]

        # Extract text from the resume
        print(
            f"Extracting resume :{candidate['resume_filename']} for candidate ID: {candidate_id}"
        )

        resume_text = await asyncio.to_thread(extract_resume_text, resume_path)

        if not resume_text.strip():
            raise ValueError(
                f"Resume text extraction failed for candidate ID: {candidate_id}"
            )

        print("Resume text extraction successful.")

        # Extract candidate data using LLM
        candidate_data = await extract_candidate_data(resume_text)

        print(f"LLM extraction successful")

        await candidates_collection.update_one(
            {"_id": candidate_object_id},
            {
                "$set": {
                    "name": candidate_data.name,
                    "email": candidate_data.email,
                    "skills": candidate_data.skills,
                    "years_of_experience": (candidate_data.years_of_experience),
                    "education": [
                        education.model_dump() for education in candidate_data.education
                    ],
                    "error": None,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        print(f"🎉 Candidate {candidate_id} " "data extracted successfully")

        # Generate embedding for the resume text
        embedding = await generate_embedding(resume_text)

        logging.info(f"Embedding generated for candidate {candidate_id}")

        # Store the embedding in Qdrant
        await store_candidate_embedding(
            candidate_id=candidate_id,
            embedding=embedding,
            payload={
                "candidate_id": candidate_id,
                "job_id": candidate["job_id"],
                "name": candidate_data.name,
                "email": candidate_data.email,
                "skills": candidate_data.skills,
            },
        )

        updated_candidate = await candidates_collection.find_one(
            {"_id": candidate_object_id}
        )

        screening_result = await screen_candidate(
            candidate=updated_candidate,
            job=job,
            resume_text=resume_text,
        )

        await candidates_collection.update_one(
            {"_id": candidate_object_id},
            {
                "$set": {
                    "screening_score": screening_result["screening_score"],
                    "semantic_similarity": screening_result["semantic_similarity"],
                    "skill_score": screening_result["skill_score"],
                    "experience_score": screening_result["experience_score"],
                    "matched_skills": screening_result["matched_skills"],
                    "missing_skills": screening_result["missing_skills"],
                    "screening_rationale": screening_result["rationale"],
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        # Send application received email if email is available
        if candidate_data.email:
            try:
                job_title = job.get("title", "the applied position")
                await send_application_received_email(
                    candidate_email=candidate_data.email,
                    candidate_name=candidate_data.name,
                    job_title=job_title,
                )
                # Mark email as sent
                await candidates_collection.update_one(
                    {"_id": candidate_object_id},
                    {
                        "$set": {
                            "email_status": "sent",
                            "email_sent_at": datetime.utcnow(),
                            "email_error": None,
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )
            except Exception as email_error:
                print(
                    f" Error sending email to candidate {candidate_id}: {email_error}"
                )

                await candidates_collection.update_one(
                    {"_id": candidate_object_id},
                    {
                        "$set": {
                            "email_status": "failed",
                            "email_error": str(email_error),
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )
        else:

            print(" Candidate email not found, skipping email sending.")

            await candidates_collection.update_one(
                {"_id": candidate_object_id},
                {
                    "$set": {
                        "email_status": "not_found",
                        "email_error": "Candidate email not found.",
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

        await candidates_collection.update_one(
            {"_id": candidate_object_id},
            {
                "$set": {
                    "status": "processed",
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        print(f"🎉 Candidate {candidate_id} " "processed successfully")
    except Exception as e:
        print(f"❌ Error processing candidate {candidate_id}: {e}")

        await candidates_collection.update_one(
            {"_id": candidate_object_id},
            {
                "$set": {
                    "status": "error",
                    "error": str(e),
                    "updated_at": datetime.utcnow(),
                }
            },
        )

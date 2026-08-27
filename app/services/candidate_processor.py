import asyncio
from datetime import datetime
from bson import ObjectId

from app.db.mongodb import candidates_collection
from app.services.resume_parser import extract_resume_text
from app.services.llm_extractor import extract_candidate_data
from app.services.email_service import send_application_received_email

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
                    "status": "processed",
                    "error": None,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        print(f"🎉 Candidate {candidate_id} " "processed successfully")

        # Send application received email if email is available
        if candidate_data.email:
            try:
                job = await candidates_collection.find_one(
                    {"_id": ObjectId(candidate["job_id"])}
                )
                job_title = job["title"] if job else "the applied position"
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

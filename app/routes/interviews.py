from pathlib import Path
import logging

from fastapi import (
    File,
    Form,
    UploadFile,
    UploadFile,
)
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.db.mongodb import interview_answers_collections

from app.models.interview_answer import create_interview_answer_document

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/interviews",
    tags=["interviews"],
)

ANSWER_UPLOAD_DIR = Path("uploads/interview_answers")
ANSWER_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/answers")
async def upload_interview_answer(
    session_id: str = Form(...),
    question_id: str = Form(...),
    answer: UploadFile = File(...),
):
    allowed_types = {
        "video/webm",
        "video/mp4",
    }

    if answer.content_type not in allowed_types:
        raise HTTPException(
            status_code=400, detail="Only WebM or MP4 video is allowed."
        )

    # create a unique filename to avoid overwriting

    filename = f"{session_id}_{question_id}.webm"

    file_path = ANSWER_UPLOAD_DIR / filename

    # save video to disk

    content = await answer.read()
    with open(file_path, "wb") as f:
        f.write(content)

    logger.info(f"Interview answer saved: {file_path}")

    # create a document for MongoDB
    document = create_interview_answer_document(
        session_id=session_id,
        question_id=question_id,
        filename=filename,
        file_path=str(file_path),
    )

    result = await interview_answers_collections.insert_one(document)

    logger.info(f"Interview answer document inserted with ID: {result.inserted_id}")

    return {
        "id": str(result.inserted_id),
        "session_id": session_id,
        "question_id": question_id,
        "filename": filename,
        "status": "uploaded",
    }


@router.get("/{session_id}/questions/{question_id}/answers")
async def get_interview_answer(session_id: str, question_id: str):
    answer = await interview_answers_collections.find_one(
        {
            "session_id": session_id,
            "question_id": question_id,
        }
    )

    if not answer:
        raise HTTPException(
            status_code=404,
            detail="Interview answer not found.",
        )

    file_path = Path(answer["file_path"])

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Video file not found",
        )

    return FileResponse(
        path=file_path,
        media_type="video/webm",
        filename=answer["filename"],
    )

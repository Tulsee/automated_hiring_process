import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.resume_parser import extract_resume_text
from app.services.llm_extractor import extract_candidate_data


async def main():

    resume_path = PROJECT_ROOT / "uploads" / "Shankar_Ghimire_CV.pdf"

    resume_text = extract_resume_text(resume_path)

    candidate = await extract_candidate_data(resume_text)

    print("\n========== STRUCTURED CANDIDATE ==========\n")

    print(candidate.model_dump_json(indent=2))

    print("\n===========================================\n")


if __name__ == "__main__":
    asyncio.run(main())

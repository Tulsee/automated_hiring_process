import json

from ollama import AsyncClient

from app.schemas.candidate import CandidateExtraction

OLLAMA_MODEL = "qwen3.5:4b"

SYSTEM_PROMPT = """
You are a resume information extraction system.
Extract information from the provided resume text.
Return ONLY valid JSON.
The JSON must follow this exact structure:

{
    "name": "string or null",
    "email": "string or null",
    "skills": ["list of strings"],
    "years_of_experience": "float or null",
    "education": [
        {
            "degree": "string or null",
            "institution": "string or null",
            "year": "string or null"
        }
    ]
}

Rules:

1. Do no invert information.
2. If information is missing, use null for that field.
3. Extract skills explicitly mentioned in the resume.
4. Estimate total years of professional experience only when the resume contaions enough information to make resonable calculation.
5. Do not count education years as work experience.
6. Keep education entries separate.
"""


async def extract_candidate_data(
    resume_text: str,
) -> CandidateExtraction:

    client = AsyncClient()

    response = await client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": resume_text},
        ],
        format="json",
        think=False,
    )

    content = response["message"]["content"]
    data = json.loads(content)

    return CandidateExtraction.model_validate(data)

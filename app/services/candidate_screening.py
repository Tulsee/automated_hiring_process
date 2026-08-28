from app.services.embedding_service import generate_embedding
from app.services.qdrant_service import search_candidate_similarity
from app.services.screening_service import (
    calculate_skill_score,
    calculate_experience_score,
    calculate_screening_score,
)


async def screen_candidate(candidate: dict, job: dict, resume_text: str):
    job_text = (
        f"{job['title']} \n\n"
        f"{job['description']} \n\n"
        f"required skills: "
        f"{', '.join(job.get('required_skills', []))}"
    )

    job_embedding = await generate_embedding(job_text)

    # Calculate semantic similarity score
    similarity = await search_candidate_similarity(
        job_embedding=job_embedding, candidate_id=str(candidate["_id"])
    )

    if similarity is None:
        raise ValueError("No similarity found for candidate '%s' in collection '%s'")

    similarity_score = max(
        0,
        min(similarity * 100, 100),
    )

    # Skill score
    skill_score = calculate_skill_score(
        candidate_skills=candidate.get(
            "skills",
            [],
        ),
        required_skills=job.get(
            "required_skills",
            [],
        ),
    )
    # Experience score
    experience_score = calculate_experience_score(
        candidate_experience=candidate.get("years_of_experience"),
        minimum_experience=job.get(
            "minimum_experience",
            0,
        ),
    )

    # Final score
    final_score = calculate_screening_score(
        similarity_score=similarity_score,
        skill_score=skill_score,
        experience_score=experience_score,
    )

    # Matched skills
    candidate_skills = {
        skill.lower()
        for skill in candidate.get(
            "skills",
            [],
        )
    }

    required_skills = {
        skill.lower()
        for skill in job.get(
            "required_skills",
            [],
        )
    }

    matched_skills = candidate_skills & required_skills

    missing_skills = required_skills - candidate_skills

    # Human-readable rationale
    rationale = (
        f"Candidate scored {final_score:.1f}/100. "
        f"Semantic resume-job similarity was "
        f"{similarity_score:.1f}%. "
        f"Matched {len(matched_skills)} of "
        f"{len(required_skills)} required skills. "
    )

    if missing_skills:
        rationale += (
            f"Missing required skills: " f"{', '.join(sorted(missing_skills))}. "
        )
    else:
        rationale += "All required skills were found. "

    candidate_experience = candidate.get("years_of_experience")

    minimum_experience = job.get(
        "minimum_experience",
        0,
    )

    rationale += (
        f"Candidate has approximately "
        f"{candidate_experience or 0} years of "
        f"experience against a minimum of "
        f"{minimum_experience} years."
    )

    return {
        "screening_score": round(
            final_score,
            2,
        ),
        "semantic_similarity": round(
            similarity_score,
            2,
        ),
        "skill_score": round(
            skill_score,
            2,
        ),
        "experience_score": round(
            experience_score,
            2,
        ),
        "matched_skills": sorted(matched_skills),
        "missing_skills": sorted(missing_skills),
        "rationale": rationale,
    }

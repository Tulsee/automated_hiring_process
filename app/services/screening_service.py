from app.services.embedding_service import generate_embedding


def calculate_skill_score(
    candidate_skills: list[str], required_skills: list[str]
) -> float:
    if not required_skills:
        return 100.0

    candidate_skills_normalized = {skill.strip().lower() for skill in candidate_skills}
    required_skills_normalized = {skill.strip().lower() for skill in required_skills}

    matched_skills = candidate_skills_normalized & required_skills_normalized
    return (len(matched_skills) / len(required_skills_normalized)) * 100


def calculate_experience_score(
    candidate_experience: float | None, minimum_experience: float | None
) -> float:
    if minimum_experience <= 0:
        return 100.0

    if candidate_experience is None:
        return 0.0

    if candidate_experience >= minimum_experience:
        return 100.0

    return (candidate_experience / minimum_experience) * 100


def calculate_screening_score(
    similarity_score: float, skill_score: float, experience_score: float
) -> float:

    return similarity_score * 0.5 + skill_score * 0.3 + experience_score * 0.2

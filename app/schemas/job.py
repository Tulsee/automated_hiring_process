from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    title: str = Field(..., example="Software Engineer")
    description: str = Field(
        ..., example="Responsible for developing software applications."
    )
    required_skills: list[str] = Field(default_factory=list)
    minimum_experience: float = 0


class JobResponse(JobCreate):
    id: str = Field(..., example="64b8f1c2e4b0f5a1c2d3e4f5")

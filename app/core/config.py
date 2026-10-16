from pathlib import Path

from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):

    MONGO_URI: str
    MONGO_DB: str

    QDRANT_URL: str
    QDRANT_COLLECTION: str

    EMBEDDING_DIMENSION: int

    LOG_LEVEL: str = "INFO"

    # Where the candidate-facing interview page is reachable, used to build
    # invite links.
    APP_BASE_URL: str = "http://127.0.0.1:8010"

    # How long an interview invite stays usable.
    INTERVIEW_INVITE_TTL_HOURS: int = 72

    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    EMAIL_FROM: str

    QDRANT_URL: str
    QDRANT_COLLECTION: str
    EMBED_MODEL: str

    class Config:
        env_file = PROJECT_ROOT / ".env"


settings = Settings()

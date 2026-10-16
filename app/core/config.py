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

    # Speech-to-text. Larger models are more accurate but much slower on CPU:
    # tiny < base < small < medium. Device "auto" picks cuda when available.
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "auto"
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_BEAM_SIZE: int = 5

    # Answers shorter than this are flagged rather than trusted.
    MIN_TRANSCRIPT_WORDS: int = 5

    # Model used to score interview answers against the rubric.
    SCORING_MODEL: str = "qwen3.5:4b"

    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    EMAIL_FROM: str

    EMBED_MODEL: str

    class Config:
        env_file = PROJECT_ROOT / ".env"


settings = Settings()

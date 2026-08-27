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

    class Config:
        env_file = PROJECT_ROOT / ".env"


settings = Settings()

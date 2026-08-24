from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    MONGO_URI: str
    MONGO_DB: str

    QDRANT_URL: str
    QDRANT_COLLECTION: str

    EMBEDDING_DIMENSION: int

    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()

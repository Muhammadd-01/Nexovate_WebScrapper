"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    GOOGLE_API_KEY: str = ""  # Optional – only needed for PageSpeed Insights
    MONGODB_URI: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "lead_intelligence"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()

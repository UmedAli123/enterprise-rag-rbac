"""Configuration settings for Enterprise RAG with RBAC."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    JWT_SECRET: str = "super-secret-jwt-key-change-in-production"
    JWT_EXPIRE_MINUTES: int = 60
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    QDRANT_PATH: str = "./qdrant_data"
    DATA_DIR: str = "./data"
    TOP_K: int = 5
    DEMO_PASSWORD: str = "nexora123"
    DEMO_MODE: bool = True
    PRICE_PER_M_INPUT_TOKENS: float = 0.075
    PRICE_PER_M_OUTPUT_TOKENS: float = 0.30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

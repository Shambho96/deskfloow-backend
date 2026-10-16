from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import os

class Settings(BaseSettings):
    APP_NAME: str = "DeskFlow Hotel PMS API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000

    JWT_SECRET: str = "deskflow_super_secret_jwt_key_2026_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    PII_SECRET_KEY: str = "c3VwZXJfc2VjcmV0X3BpaV9rZXlfMzJfYnl0ZXNfbG9uZw=="

    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/deskflow_db"
    SQL_ECHO: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

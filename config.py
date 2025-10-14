"""
Configuration management for the Code Agent service.
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000

    # Upload Configuration
    max_upload_size: int = 52428800  # 50MB
    temp_dir: str = "./temp"

    # Gemini CLI Configuration
    gemini_api_key: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()

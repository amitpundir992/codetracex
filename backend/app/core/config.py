"""
Application configuration loaded from environment variables.
"""
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load .env file from backend directory
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)


class Settings:
    """Application settings loaded from environment variables."""
    
    # Application
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    
    # CORS
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    # Database Configuration
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://codetracex_user:codetracex_dev_password@localhost:5432/codetracex"
    )
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    
    # Repository Analysis Limits
    # Maximum repository download size in MB (default: 500MB)
    MAX_REPOSITORY_SIZE_MB: int = int(os.getenv("MAX_REPOSITORY_SIZE_MB", "500"))
    
    # Maximum number of files to scan (default: 10000)
    MAX_REPOSITORY_FILES: int = int(os.getenv("MAX_REPOSITORY_FILES", "10000"))
    
    @property
    def max_repository_size_bytes(self) -> int:
        """Convert MAX_REPOSITORY_SIZE_MB to bytes."""
        return self.MAX_REPOSITORY_SIZE_MB * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses lru_cache to ensure settings are loaded once and reused.
    """
    return Settings()

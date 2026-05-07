"""
TelcoPulse - Core Configuration
Updated for AWS RDS PostgreSQL Integration
"""

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # ── Application ─────────────────────────────────────────────────────────
    APP_NAME: str = "TelcoPulse"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True  

    # ── Database (AWS RDS Settings) ───────────────────────────────────────────
    POSTGRES_USER: str = "postgres" 
    POSTGRES_PASSWORD: str = "Anass12345" 
    POSTGRES_DB: str = "postgres" 
    POSTGRES_HOST: str = "telcopulse-db.cpdtr4jah3fj.us-east-1.rds.amazonaws.com"
    POSTGRES_PORT: int = 5432

    @property
    def DATABASE_URL(self) -> str:
        """Async connection string for AWS PostgreSQL with SSL."""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}?ssl=require"

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Sync connection string for AWS PostgreSQL with SSL."""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}?sslmode=require"

    # ── Monitoring Worker ─────────────────────────────────────────────────────
    MONITOR_INTERVAL_SECONDS: int = 60
    HTTP_TIMEOUT_SECONDS: float = 20.0
    HTTP_MAX_RETRIES: int = 3
    HTTP_RETRY_WAIT_SECONDS: float = 2.0

    # ── Rate Limiting ────────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()
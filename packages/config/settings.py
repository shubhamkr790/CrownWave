from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # -- Database --
    database_url: str = "postgresql+asyncpg://cronwave:cronwave@localhost:5432/cronwave"
    database_pool_size: int = 10
    database_max_overflow: int = 5

    # -- Redis --
    redis_url: str = "redis://localhost:6379/0"

    # -- Auth --
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 7

    # -- API --
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1

    # -- Worker --
    worker_concurrency: int = 4
    worker_poll_interval_sec: float = 2.0
    worker_heartbeat_interval_sec: float = 30.0
    # If a worker hasn't heartbeated in this window, its jobs are considered abandoned.
    worker_heartbeat_timeout_sec: float = 90.0
    worker_claim_batch_size: int = 5

    # -- Scheduler --
    scheduler_tick_interval_sec: float = 15.0

    # -- Environment --
    environment: str = "development"
    log_level: str = "INFO"
    log_format: str = "console"  # "console" or "json"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def sync_database_url(self) -> str:
        """Alembic needs a sync URL. Swap asyncpg for psycopg2."""
        return self.database_url.replace("+asyncpg", "+psycopg2")


@lru_cache
def get_settings() -> Settings:
    return Settings()

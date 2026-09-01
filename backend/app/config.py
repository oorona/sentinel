from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import json
from pathlib import Path


def _read_secret(name: str) -> str:
    """
    Read a Docker secret from /run/secrets/<name>.
    Returns empty string if the file does not exist (local dev fallback).
    """
    path = Path(f"/run/secrets/{name}")
    if path.exists():
        return path.read_text().strip()
    return ""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    APP_NAME: str = "AIOps Sentinel"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database — non-sensitive parts only (env vars per spec)
    # Password is a Docker secret — never set in env in production
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "sentinel"
    POSTGRES_USER: str = "sentinel"
    POSTGRES_PASSWORD: str = ""  # local dev only; overridden by Docker secret at runtime

    # Redis (env var per spec)
    REDIS_URL: str = "redis://sentinel-redis:6379/0"

    # Prometheus (env var per spec)
    PROMETHEUS_URL: str = "http://prometheus:9090"
    PROMETHEUS_POLL_INTERVAL_SECONDS: int = 30
    PROMETHEUS_LOOKBACK_MINUTES: int = 60

    # Loki (env var per spec)
    LOKI_URL: str = "http://loki:3100"
    LOKI_LOG_LINES: int = 100
    LOKI_POLL_INTERVAL_SECONDS: int = 5

    # Gemini — key is a Docker secret; local dev can use .env fallback
    GEMINI_API_KEY: str = ""  # overridden by Docker secret at runtime
    GEMINI_FLASH_MODEL: str = "gemini-3-flash-preview"
    GEMINI_PRO_MODEL: str = "gemini-3-pro-preview"
    GEMINI_THINKING_BUDGET: int = 15000
    GEMINI_THINKING_BUDGET_MEDIUM: int = 8000

    # MAD/CUSUM thresholds
    MAD_ZSCORE_THRESHOLD: float = 3.5
    CUSUM_SLACK_MULTIPLIER: float = 0.5
    CUSUM_ALARM_THRESHOLD: float = 4.0
    LEARNING_WINDOW_DAYS: int = 30

    # Incident timeouts
    EXPECTED_OVERRUN_MULTIPLIER: float = 1.2

    def model_post_init(self, __context) -> None:
        """
        Override sensitive fields with Docker secrets at runtime.
        Secrets are mounted at /run/secrets/<name> as plain text files.
        Falls back to the field default (local dev .env) when secrets are not present.
        """
        gemini_key = _read_secret("gemini_api_key")
        if gemini_key:
            object.__setattr__(self, "GEMINI_API_KEY", gemini_key)

        db_password = _read_secret("postgres_password")
        if db_password:
            object.__setattr__(self, "POSTGRES_PASSWORD", db_password)

    @property
    def database_url(self) -> str:
        """Build the async PostgreSQL connection URL using the resolved password."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def gemini_response_schema(self) -> dict:
        schema_path = Path(__file__).parent.parent.parent.parent / "specs" / "gemini_response_schema.json"
        if schema_path.exists():
            return json.loads(schema_path.read_text())
        return {
            "type": "object",
            "properties": {
                "is_anomaly": {"type": "boolean"},
                "severity": {"type": "string", "enum": ["INFO", "WARNING", "CRITICAL"]},
                "root_cause_analysis": {"type": "string"},
                "detected_errors": {"type": "array", "items": {"type": "string"}},
                "remediation_steps": {"type": "array", "items": {"type": "string"}},
                "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["is_anomaly", "severity", "root_cause_analysis", "confidence_score"],
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()

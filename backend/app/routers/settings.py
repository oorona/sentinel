"""
Settings Router: Expose current runtime configuration and test connectivity.

  GET  /api/v1/settings          — Non-sensitive runtime config (URLs, models, thresholds)
  POST /api/v1/settings/test-db  — Test database connection and verify schema tables
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database import get_db
from app.config import get_settings

router = APIRouter(prefix="/settings", tags=["settings"])
logger = logging.getLogger(__name__)
settings = get_settings()

REQUIRED_TABLES = [
    "targets",
    "metric_profiles",
    "incident_history",
    "prompt_templates",
]


@router.get("")
async def get_config():
    """Return current non-sensitive runtime configuration."""
    return {
        "database": {
            "host": settings.POSTGRES_HOST,
            "port": settings.POSTGRES_PORT,
            "name": settings.POSTGRES_DB,
            "user": settings.POSTGRES_USER,
        },
        "services": {
            "redis_url": settings.REDIS_URL,
            "prometheus_url": settings.PROMETHEUS_URL,
            "loki_url": settings.LOKI_URL,
        },
        "ai": {
            "pro_model": settings.GEMINI_PRO_MODEL,
            "flash_model": settings.GEMINI_FLASH_MODEL,
            "thinking_budget": settings.GEMINI_THINKING_BUDGET,
            "thinking_budget_medium": settings.GEMINI_THINKING_BUDGET_MEDIUM,
            "api_key_configured": bool(settings.GEMINI_API_KEY),
        },
        "monitoring": {
            "poll_interval_seconds": settings.PROMETHEUS_POLL_INTERVAL_SECONDS,
            "lookback_minutes": settings.PROMETHEUS_LOOKBACK_MINUTES,
            "loki_log_lines": settings.LOKI_LOG_LINES,
            "loki_poll_interval_seconds": settings.LOKI_POLL_INTERVAL_SECONDS,
            "mad_zscore_threshold": settings.MAD_ZSCORE_THRESHOLD,
            "cusum_slack_multiplier": settings.CUSUM_SLACK_MULTIPLIER,
            "cusum_alarm_threshold": settings.CUSUM_ALARM_THRESHOLD,
            "expected_overrun_multiplier": settings.EXPECTED_OVERRUN_MULTIPLIER,
            "learning_window_days": settings.LEARNING_WINDOW_DAYS,
        },
    }


@router.post("/test-db")
async def test_database(db: AsyncSession = Depends(get_db)):
    """
    Test database connectivity and verify the expected schema tables exist.
    Returns connection status, per-table presence, and current Alembic revision.
    """
    try:
        await db.execute(text("SELECT 1"))

        result = await db.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        existing = {row[0] for row in result.fetchall()}

        tables = {t: t in existing for t in REQUIRED_TABLES}
        schema_ok = all(tables.values())

        alembic_version: str | None = None
        if "alembic_version" in existing:
            ver = await db.execute(text("SELECT version_num FROM alembic_version"))
            row = ver.fetchone()
            alembic_version = row[0] if row else None

        return {
            "connected": True,
            "schema_ok": schema_ok,
            "tables": tables,
            "alembic_version": alembic_version,
        }

    except Exception as e:
        logger.error(f"Database test failed: {e}")
        return {
            "connected": False,
            "schema_ok": False,
            "error": str(e),
        }

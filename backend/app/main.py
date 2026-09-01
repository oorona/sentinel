"""
AIOps Sentinel — FastAPI Backend
"""
import asyncio
import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.redis_client import get_redis, close_redis
from app.routers import incidents, targets, history, prompts, settings as settings_router
from app.workers.monitoring_worker import monitoring_loop
from app.services.sse_manager import broadcast, SSEEvents
from app.models import Target, MetricProfile, IncidentHistory, PromptTemplate

settings = get_settings()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Startup
    logger.info("Starting AIOps Sentinel backend...")

    # Ensure Redis connection
    redis = await get_redis()
    await redis.ping()
    logger.info("Redis connection established.")

    # Seed default prompt template if none exists
    await _seed_default_prompt()

    # Start monitoring worker
    worker_task = asyncio.create_task(monitoring_loop())
    logger.info("Monitoring worker started.")

    yield

    # Shutdown
    logger.info("Shutting down AIOps Sentinel...")
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    await close_redis()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="AIOps Sentinel API",
    description="Self-aware observability platform with MAD/CUSUM anomaly detection and Gemini 3.0 reasoning.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tightened in production via Traefik
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(incidents.router, prefix=settings.API_V1_PREFIX)
app.include_router(targets.router, prefix=settings.API_V1_PREFIX)
app.include_router(history.router, prefix=settings.API_V1_PREFIX)
app.include_router(prompts.router, prefix=settings.API_V1_PREFIX)
app.include_router(settings_router.router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "sentinel-api"}


@app.get("/api/v1/status")
async def system_status():
    """System health summary."""
    redis = await get_redis()
    try:
        await redis.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    return {
        "api": "ok",
        "redis": "ok" if redis_ok else "error",
    }


async def _seed_default_prompt():
    """Seed the default Gemini system prompt template on first run."""
    from app.database import AsyncSessionLocal
    from app.models.prompt_template import PromptTemplate
    from sqlalchemy import select
    from pathlib import Path
    import json

    default_system = Path(__file__).parent.parent.parent / "specs" / "gemini_thinking_system_prompt.txt"
    default_schema = Path(__file__).parent.parent.parent / "specs" / "gemini_response_schema.json"

    system_text = default_system.read_text() if default_system.exists() else "You are an SRE AI assistant."
    schema_dict = json.loads(default_schema.read_text()) if default_schema.exists() else {}

    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(PromptTemplate).where(PromptTemplate.name == "default"))
        if not existing.scalar_one_or_none():
            template = PromptTemplate(
                name="default",
                system_message=system_text,
                json_schema=schema_dict,
                is_active=True,
            )
            db.add(template)
            await db.commit()
            logger.info("Default prompt template seeded.")

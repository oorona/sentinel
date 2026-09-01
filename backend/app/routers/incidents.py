"""
Incidents Router:
  GET  /api/v1/incidents/stream     — SSE stream for real-time UI updates
  GET  /api/v1/incidents/active     — List all active incidents from Redis
  POST /api/v1/incidents/{id}/ack   — Acknowledge an incident
  GET  /api/v1/incidents/{id}/logs  — Get buffered logs for an incident
"""
import json
import time
from typing import Optional

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.database import get_db
from app.redis_client import get_redis, get_all_active_incidents, get_log_buffer
from app.schemas.incident import IncidentAcknowledge
from app.services.sse_manager import event_generator
from app.services.incident_manager import acknowledge_incident

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("/stream")
async def incident_stream(request: Request):
    """
    Server-Sent Events endpoint. Browser connects here to receive real-time updates.
    """
    async def generator():
        async for event in event_generator(request):
            event_type = event.get("event", "update")
            data = event.get("data", "{}")
            yield f"event: {event_type}\ndata: {data}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/active")
async def get_active_incidents(
    redis: aioredis.Redis = Depends(get_redis),
):
    """Return all currently active incidents from Redis."""
    incidents = await get_all_active_incidents(redis)
    now = time.time()
    result = []
    for inc in incidents:
        inc_copy = dict(inc)
        # Compute remaining countdown
        expected_end = inc_copy.get("expected_end_ts")
        if expected_end:
            try:
                inc_copy["countdown_sec"] = max(0, float(expected_end) - now)
            except (ValueError, TypeError):
                inc_copy["countdown_sec"] = None
        result.append(inc_copy)
    return result


@router.post("/{incident_id}/ack")
async def ack_incident(
    incident_id: str,
    body: IncidentAcknowledge,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Acknowledge an incident — moves it to history."""
    await acknowledge_incident(db, redis, incident_id, notes=body.notes)
    return {"status": "acknowledged", "incident_id": incident_id}


@router.get("/{incident_id}/logs")
async def get_incident_logs(
    incident_id: str,
    redis: aioredis.Redis = Depends(get_redis),
):
    """Retrieve buffered log lines for a specific incident."""
    logs = await get_log_buffer(redis, incident_id)
    return {"incident_id": incident_id, "logs": logs}

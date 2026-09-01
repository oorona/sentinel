"""
Incident Manager: Orchestrates the lifecycle of an incident.

Responsibilities:
- Create incidents in Redis (volatile state) and PostgreSQL (history).
- Classify incidents against the knowledge base (MetricProfile).
- Trigger Gemini analysis when warranted.
- Broadcast SSE events for real-time UI updates.
"""
import asyncio
import json
import logging
import time
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.target import Target, MetricProfile
from app.models.incident import IncidentHistory
from app.redis_client import (
    set_active_incident,
    get_active_incident,
    delete_active_incident,
    push_log_to_buffer,
    get_log_buffer,
)
from app.services.sse_manager import broadcast, SSEEvents
from app.services.gemini_service import gemini_service
from app.services.math_engine import AnomalySignal, matches_profile
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def create_incident(
    db: AsyncSession,
    redis,
    target: Target,
    signal: AnomalySignal,
    metrics_context: dict,
) -> dict:
    """
    Create a new incident card.
    1. Checks knowledge base for profile match.
    2. Creates Redis active incident record.
    3. Creates PostgreSQL history record.
    4. Broadcasts SSE incident_created event.
    Returns the incident dict.
    """
    incident_id = str(uuid.uuid4())
    now = time.time()

    # -- Knowledge base lookup --
    classification = "detecting"
    expected_end_ts = None
    profile_name = None
    matched_profile_id = None

    profiles_result = await db.execute(
        select(MetricProfile).where(MetricProfile.target_id == target.id)
    )
    profiles = profiles_result.scalars().all()

    for profile in profiles:
        profile_dict = {
            "mean_peak_cpu": profile.mean_peak_cpu,
            "mean_integral": profile.mean_integral,
            "expected_duration_minutes": profile.expected_duration_minutes,
        }
        if matches_profile(signal, profile_dict):
            classification = "expected"
            profile_name = profile.profile_name
            matched_profile_id = profile.id
            expected_end_ts = now + profile.expected_duration_minutes * 60
            break

    if classification == "detecting":
        classification = "unexpected"

    # -- Redis record --
    redis_data = {
        "id": incident_id,
        "target_id": str(target.id),
        "target_name": target.display_name,
        "target_env": target.environment,
        "target_priority": target.priority,
        "classification": classification,
        "status": "active",
        "start_ts": now,
        "expected_end_ts": expected_end_ts or "",
        "current_metric_value": signal.peak_value,
        "profile_name": profile_name or "",
        "mad_zscore": signal.modified_z_score,
        "cusum_upper": signal.cusum_upper,
    }

    ttl = int(expected_end_ts - now) + 7200 if expected_end_ts else 86400
    await set_active_incident(redis, incident_id, redis_data, ttl_seconds=ttl)

    # -- PostgreSQL history record --
    from datetime import datetime
    db_incident = IncidentHistory(
        id=uuid.UUID(incident_id),
        target_id=target.id,
        start_ts=datetime.utcfromtimestamp(now),
        classification=classification,
        final_status="active",
        is_anomaly=(classification == "unexpected"),
        raw_metrics=metrics_context,
        matched_profile_id=matched_profile_id,
    )
    db.add(db_incident)
    await db.commit()

    # -- SSE broadcast --
    sse_payload = {
        "id": incident_id,
        "target_id": str(target.id),
        "target_name": target.display_name,
        "target_env": target.environment,
        "target_priority": target.priority,
        "classification": classification,
        "status": "active",
        "start_ts": now,
        "expected_end_ts": expected_end_ts,
        "profile_name": profile_name,
        "mad_zscore": round(signal.modified_z_score, 2),
    }
    await broadcast(SSEEvents.INCIDENT_CREATED, sse_payload)

    logger.info(f"Incident {incident_id} created for {target.display_name}: {classification}")
    return redis_data


async def run_gemini_analysis(
    db: AsyncSession,
    redis,
    incident_id: str,
    target: Target,
    metrics_context: dict,
    logs_snapshot: str,
    history_context: Optional[dict],
    trigger_reason: str = "Anomaly detected",
    system_prompt_override: Optional[str] = None,
    schema_override: Optional[dict] = None,
):
    """
    Run Gemini Pro thinking analysis for an incident.
    Streams thinking blocks and final structured verdict via SSE.
    Persists results to PostgreSQL.
    """
    # Update incident status to "analyzing"
    active = await get_active_incident(redis, incident_id)
    if active:
        active["status"] = "analyzing"
        await set_active_incident(redis, incident_id, active)

    await broadcast(SSEEvents.INCIDENT_UPDATE, {
        "id": incident_id,
        "status": "analyzing",
    })

    context = {
        "target_info": {
            "name": target.display_name,
            "environment": target.environment,
            "priority": target.priority,
            "db_type": target.db_type or "unknown",
        },
        "metrics": metrics_context,
        "logs": logs_snapshot,
        "history": history_context,
        "trigger_reason": trigger_reason,
    }

    thought_buffer = ""
    structured_output = None

    try:
        async for event in gemini_service.stream_analysis(
            context=context,
            system_prompt_override=system_prompt_override,
            schema_override=schema_override,
        ):
            if event["type"] == "thought":
                thought_buffer += event["text"]
                # Stream thought to UI
                await broadcast(SSEEvents.GEMINI_THOUGHT, {
                    "id": incident_id,
                    "chunk": event["text"],
                })

            elif event["type"] == "final":
                structured_output = event["data"]
                severity = structured_output.get("severity", "WARNING")
                is_anomaly = structured_output.get("is_anomaly", True)

                # Broadcast final verdict
                await broadcast(SSEEvents.GEMINI_FINAL, {
                    "id": incident_id,
                    "structured_json": structured_output,
                })

                # Update Redis
                if active:
                    active["final_severity"] = severity
                    active["status"] = "analyzed"
                    await set_active_incident(redis, incident_id, active)

                await broadcast(SSEEvents.INCIDENT_UPDATE, {
                    "id": incident_id,
                    "status": "analyzed",
                    "severity": severity,
                })

            elif event["type"] == "error":
                logger.error(f"Gemini error for incident {incident_id}: {event['text']}")
                await broadcast(SSEEvents.INCIDENT_UPDATE, {
                    "id": incident_id,
                    "status": "analysis_error",
                    "error": event["text"],
                })

        # -- Persist to PostgreSQL --
        from datetime import datetime
        result = await db.execute(
            select(IncidentHistory).where(IncidentHistory.id == uuid.UUID(incident_id))
        )
        db_incident = result.scalar_one_or_none()
        if db_incident:
            db_incident.llm_thought_process = thought_buffer
            db_incident.llm_structured_output = structured_output
            db_incident.loki_logs_snapshot = logs_snapshot
            if structured_output:
                db_incident.final_severity = structured_output.get("severity")
                db_incident.is_anomaly = structured_output.get("is_anomaly", True)
            await db.commit()

    except Exception as e:
        logger.error(f"run_gemini_analysis failed for {incident_id}: {e}", exc_info=True)
        await broadcast(SSEEvents.INCIDENT_UPDATE, {
            "id": incident_id,
            "status": "analysis_error",
            "error": str(e),
        })


async def acknowledge_incident(
    db: AsyncSession,
    redis,
    incident_id: str,
    notes: Optional[str] = None,
):
    """
    Acknowledge an incident: mark as ack in Redis and PostgreSQL, remove active state.
    """
    from datetime import datetime

    # Update PostgreSQL
    result = await db.execute(
        select(IncidentHistory).where(IncidentHistory.id == uuid.UUID(incident_id))
    )
    db_incident = result.scalar_one_or_none()
    if db_incident:
        db_incident.final_status = "ack"
        db_incident.end_ts = datetime.utcnow()
        await db.commit()

    # Remove from Redis active incidents
    await delete_active_incident(redis, incident_id)

    await broadcast(SSEEvents.INCIDENT_UPDATE, {
        "id": incident_id,
        "status": "acknowledged",
    })

    logger.info(f"Incident {incident_id} acknowledged.")


async def resolve_incident(db: AsyncSession, redis, incident_id: str):
    """Auto-resolve: CPU dropped back to baseline, event completed normally."""
    from datetime import datetime

    result = await db.execute(
        select(IncidentHistory).where(IncidentHistory.id == uuid.UUID(incident_id))
    )
    db_incident = result.scalar_one_or_none()
    if db_incident:
        db_incident.final_status = "resolved"
        db_incident.end_ts = datetime.utcnow()
        await db.commit()

    await delete_active_incident(redis, incident_id)

    await broadcast(SSEEvents.INCIDENT_UPDATE, {
        "id": incident_id,
        "status": "resolved",
    })

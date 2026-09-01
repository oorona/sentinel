"""
Monitoring Worker: The main polling loop.

Every PROMETHEUS_POLL_INTERVAL_SECONDS:
  1. Query all configured targets from Prometheus.
  2. Run MAD/CUSUM analysis.
  3. If spike detected → check Redis for active incident → classify against KB → create card.
  4. Stream Loki logs for active incidents to SSE.
  5. Check expected-event overruns → escalate to Gemini.
"""
import asyncio
import logging
import time
from typing import Optional

from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.target import Target, MetricProfile
from app.models.incident import IncidentHistory
from app.redis_client import (
    get_redis,
    get_active_incident,
    get_all_active_incidents,
    push_log_to_buffer,
    set_active_incident,
)
from app.services.math_engine import detect_anomaly, extract_spike_profile, build_or_update_profile
from app.services.prometheus_client import PrometheusClient
from app.services.loki_client import LokiClient
from app.services.sse_manager import broadcast, SSEEvents
from app.services.incident_manager import (
    create_incident,
    run_gemini_analysis,
    resolve_incident,
)

logger = logging.getLogger(__name__)
settings = get_settings()

prometheus = PrometheusClient()
loki = LokiClient()

# Track last Loki poll timestamp per incident
_loki_last_poll: dict[str, float] = {}


async def poll_target(target: Target, db, redis):
    """
    Poll one target: query metrics, run detection, manage incident lifecycle.
    """
    try:
        timestamps, values = await prometheus.get_cpu_timeseries(
            target.prom_label,
            lookback_minutes=settings.PROMETHEUS_LOOKBACK_MINUTES,
            step=settings.PROMETHEUS_POLL_INTERVAL_SECONDS,
        )
    except Exception as e:
        logger.warning(f"Prometheus query failed for {target.display_name}: {e}")
        return

    if not timestamps or len(timestamps) < 5:
        logger.debug(f"Insufficient data for {target.display_name}, skipping.")
        return

    # Fetch baseline from most recent profile if available
    profile_result = await db.execute(
        select(MetricProfile)
        .where(MetricProfile.target_id == target.id)
        .order_by(MetricProfile.last_updated.desc())
        .limit(1)
    )
    latest_profile = profile_result.scalar_one_or_none()
    baseline_mean = latest_profile.mean_peak_cpu * 0.5 if latest_profile else None

    # Run MAD/CUSUM
    signal = detect_anomaly(
        timestamps=timestamps,
        values=values,
        baseline_mean=baseline_mean,
        poll_interval_seconds=settings.PROMETHEUS_POLL_INTERVAL_SECONDS,
    )

    # Current metric value
    current_value = values[-1] if values else 0.0

    # Check existing active incident for this target
    active_incidents = await get_all_active_incidents(redis)
    target_incidents = [
        inc for inc in active_incidents
        if inc.get("target_id") == str(target.id) and inc.get("status") not in ("acknowledged", "resolved")
    ]
    existing_incident = target_incidents[0] if target_incidents else None

    if signal.is_anomaly:
        if existing_incident:
            incident_id = existing_incident.get("id")

            # Update current value
            existing_incident["current_metric_value"] = current_value
            await set_active_incident(redis, incident_id, existing_incident)

            await broadcast(SSEEvents.INCIDENT_UPDATE, {
                "id": incident_id,
                "current_cpu": current_value,
                "countdown_sec": _get_countdown(existing_incident),
                "status": existing_incident.get("status"),
            })

            # Check for expected overrun
            if _is_overdue(existing_incident) and existing_incident.get("status") not in ("analyzing", "analyzed", "analysis_error"):
                logger.info(f"Incident {incident_id} is OVERDUE. Triggering Gemini escalation.")
                existing_incident["classification"] = "overdue"
                await set_active_incident(redis, incident_id, existing_incident)
                await broadcast(SSEEvents.INCIDENT_UPDATE, {
                    "id": incident_id,
                    "classification": "overdue",
                    "status": "overdue",
                })

                # Gather context for Gemini
                metrics_context = _build_metrics_context(signal, timestamps, values)
                logs_snapshot = await loki.get_logs_snapshot(target.loki_label or "", lines=100)
                history_context = _build_history_context(latest_profile, existing_incident)

                asyncio.create_task(
                    run_gemini_analysis(
                        db=db,
                        redis=redis,
                        incident_id=incident_id,
                        target=target,
                        metrics_context=metrics_context,
                        logs_snapshot=logs_snapshot,
                        history_context=history_context,
                        trigger_reason=f"Expected event exceeded duration threshold (overdue by {_get_overdue_minutes(existing_incident):.0f} minutes)",
                    )
                )

        else:
            # New incident
            metrics_context = _build_metrics_context(signal, timestamps, values)
            incident = await create_incident(
                db=db,
                redis=redis,
                target=target,
                signal=signal,
                metrics_context=metrics_context,
            )
            incident_id = incident["id"]

            # Trigger Gemini immediately for unexpected events
            if incident.get("classification") == "unexpected":
                logs_snapshot = await loki.get_logs_snapshot(target.loki_label or "", lines=100)
                history_context = _build_history_context(latest_profile, None)

                asyncio.create_task(
                    run_gemini_analysis(
                        db=db,
                        redis=redis,
                        incident_id=incident_id,
                        target=target,
                        metrics_context=metrics_context,
                        logs_snapshot=logs_snapshot,
                        history_context=history_context,
                        trigger_reason="Unexpected anomaly: no matching profile in knowledge base",
                    )
                )

    else:
        # No anomaly detected — resolve any active incident for this target
        if existing_incident and existing_incident.get("status") == "active":
            incident_id = existing_incident.get("id")
            logger.info(f"Incident {incident_id} resolved: metric returned to baseline.")

            # Update profile with observed data
            if existing_incident.get("classification") in ("expected", "overdue"):
                spike_profile = extract_spike_profile(timestamps, values, signal, settings.PROMETHEUS_POLL_INTERVAL_SECONDS)
                if spike_profile and latest_profile:
                    existing_dict = {
                        "mean_peak_cpu": latest_profile.mean_peak_cpu,
                        "mean_rise_time_seconds": latest_profile.mean_rise_time_seconds,
                        "mean_integral": latest_profile.mean_integral,
                        "expected_duration_minutes": latest_profile.expected_duration_minutes,
                        "std_duration_minutes": latest_profile.std_duration_minutes,
                        "sample_count": latest_profile.sample_count,
                    }
                    updated = build_or_update_profile(existing_dict, spike_profile)
                    latest_profile.mean_peak_cpu = updated["mean_peak_cpu"]
                    latest_profile.mean_rise_time_seconds = updated["mean_rise_time_seconds"]
                    latest_profile.mean_integral = updated["mean_integral"]
                    latest_profile.expected_duration_minutes = updated["expected_duration_minutes"]
                    latest_profile.std_duration_minutes = updated["std_duration_minutes"]
                    latest_profile.sample_count = updated["sample_count"]
                    await db.commit()
                    logger.info(f"Profile '{latest_profile.profile_name}' updated with new observation (n={latest_profile.sample_count}).")

            await resolve_incident(db, redis, incident_id)


async def poll_loki_for_active_incidents(redis):
    """Stream new Loki log lines for all active incidents."""
    active_incidents = await get_all_active_incidents(redis)
    for incident in active_incidents:
        incident_id = incident.get("id")
        target_id = incident.get("target_id")
        if not incident_id:
            continue

        # Get target loki label
        async with AsyncSessionLocal() as db:
            import uuid
            result = await db.execute(select(Target).where(Target.id == uuid.UUID(target_id)))
            target = result.scalar_one_or_none()
            if not target or not target.loki_label:
                continue

        since = _loki_last_poll.get(incident_id, incident.get("start_ts", time.time() - 300))
        since_ns = int(since * 1e9)

        try:
            new_logs = await loki.tail_logs(target.loki_label, since_ns=since_ns)
        except Exception as e:
            logger.warning(f"Loki poll failed for incident {incident_id}: {e}")
            continue

        for entry in new_logs:
            log_line = entry["line"]
            ts = entry["timestamp_sec"]

            await push_log_to_buffer(redis, incident_id, log_line)
            await broadcast(SSEEvents.LOKI_LOGS, {
                "id": incident_id,
                "log_line": log_line,
                "timestamp": ts,
            })

        if new_logs:
            _loki_last_poll[incident_id] = new_logs[-1]["timestamp_sec"]
        else:
            _loki_last_poll[incident_id] = time.time()


async def monitoring_loop():
    """
    Main monitoring loop. Runs indefinitely as a background task.
    """
    logger.info("Monitoring worker started.")
    loki_tick = 0

    while True:
        try:
            redis = await get_redis()

            async with AsyncSessionLocal() as db:
                targets_result = await db.execute(select(Target))
                targets = targets_result.scalars().all()

            if not targets:
                logger.debug("No targets configured. Sleeping.")
            else:
                tasks = []
                for target in targets:
                    async with AsyncSessionLocal() as db:
                        tasks.append(poll_target(target, db, redis))
                await asyncio.gather(*tasks, return_exceptions=True)

            # Poll Loki every LOKI_POLL_INTERVAL_SECONDS
            loki_tick += settings.PROMETHEUS_POLL_INTERVAL_SECONDS
            if loki_tick >= settings.LOKI_POLL_INTERVAL_SECONDS:
                loki_tick = 0
                try:
                    await poll_loki_for_active_incidents(redis)
                except Exception as e:
                    logger.error(f"Loki polling error: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Monitoring loop error: {e}", exc_info=True)

        await asyncio.sleep(settings.PROMETHEUS_POLL_INTERVAL_SECONDS)


# ---------- Helpers ----------

def _build_metrics_context(signal, timestamps: list, values: list) -> dict:
    """Serialize anomaly signal and recent metrics for LLM context."""
    return {
        "peak_cpu_percent": round(signal.peak_value, 2),
        "mad_zscore": round(signal.modified_z_score, 2),
        "rise_time_seconds": round(signal.rise_time_seconds, 1),
        "integral": round(signal.integral, 1),
        "kurtosis": round(signal.kurtosis, 3),
        "cusum_upper": round(signal.cusum_upper, 2),
        "direction": signal.mean_shift_direction,
        "recent_values": [round(v, 2) for v in values[-20:]],
        "timestamps": timestamps[-20:],
    }


def _build_history_context(profile: Optional[MetricProfile], active_incident: Optional[dict]) -> Optional[dict]:
    if not profile:
        return None
    ctx = {
        "profile_name": profile.profile_name,
        "expected_duration_minutes": profile.expected_duration_minutes,
        "std_duration_minutes": profile.std_duration_minutes,
        "mean_peak_cpu": profile.mean_peak_cpu,
        "mean_rise_time_seconds": profile.mean_rise_time_seconds,
        "sample_count": profile.sample_count,
    }
    if active_incident:
        elapsed = time.time() - float(active_incident.get("start_ts", time.time()))
        ctx["actual_duration_minutes"] = elapsed / 60.0
        overrun = elapsed / 60.0 - profile.expected_duration_minutes
        ctx["overrun_minutes"] = max(0, overrun)
    return ctx


def _get_countdown(incident: dict) -> float:
    expected_end = incident.get("expected_end_ts")
    if not expected_end:
        return -1
    try:
        return max(0, float(expected_end) - time.time())
    except (ValueError, TypeError):
        return -1


def _is_overdue(incident: dict) -> bool:
    expected_end = incident.get("expected_end_ts")
    if not expected_end:
        return False
    try:
        elapsed = time.time() - float(incident.get("start_ts", time.time()))
        expected_duration = float(expected_end) - float(incident.get("start_ts", time.time()))
        return elapsed > expected_duration * settings.EXPECTED_OVERRUN_MULTIPLIER
    except (ValueError, TypeError):
        return False


def _get_overdue_minutes(incident: dict) -> float:
    expected_end = incident.get("expected_end_ts")
    if not expected_end:
        return 0
    try:
        return max(0, (time.time() - float(expected_end)) / 60.0)
    except (ValueError, TypeError):
        return 0

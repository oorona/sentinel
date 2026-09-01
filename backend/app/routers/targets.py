"""
Targets Router: CRUD for monitoring targets.
  GET    /api/v1/targets          — List all targets
  POST   /api/v1/targets          — Create target
  PUT    /api/v1/targets/{id}     — Update target
  DELETE /api/v1/targets/{id}     — Delete target
  GET    /api/v1/targets/{id}/profiles — List profiles for a target
  POST   /api/v1/targets/{id}/learn   — Trigger learning phase for a target
"""
import uuid
import time
import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.database import AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.target import Target, MetricProfile
from app.schemas.target import TargetCreate, TargetUpdate, TargetRead, MetricProfileRead
from app.services.prometheus_client import PrometheusClient
from app.services.math_engine import detect_anomaly, extract_spike_profile, build_or_update_profile
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/targets", tags=["targets"])
settings = get_settings()


@router.get("", response_model=list[TargetRead])
async def list_targets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Target).order_by(Target.priority.desc(), Target.display_name))
    return result.scalars().all()


@router.post("", response_model=TargetRead, status_code=201)
async def create_target(body: TargetCreate, db: AsyncSession = Depends(get_db)):
    # Check uniqueness
    existing = await db.execute(select(Target).where(Target.label_name == body.label_name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Target '{body.label_name}' already exists.")

    target = Target(**body.model_dump())
    db.add(target)
    await db.commit()
    await db.refresh(target)
    return target


@router.put("/{target_id}", response_model=TargetRead)
async def update_target(
    target_id: uuid.UUID,
    body: TargetUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Target).where(Target.id == target_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found.")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(target, field, value)
    await db.commit()
    await db.refresh(target)
    return target


@router.delete("/{target_id}", status_code=204)
async def delete_target(target_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Target).where(Target.id == target_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found.")
    await db.delete(target)
    await db.commit()


@router.get("/{target_id}/profiles", response_model=list[MetricProfileRead])
async def get_target_profiles(target_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MetricProfile).where(MetricProfile.target_id == target_id)
    )
    return result.scalars().all()


@router.post("/{target_id}/learn")
async def trigger_learning(
    target_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger the learning phase for a target.
    Queries 30 days of Prometheus data, runs MAD/CUSUM, and builds/updates profiles.
    """
    result = await db.execute(select(Target).where(Target.id == target_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found.")

    background_tasks.add_task(_run_learning_phase, target_id, target.prom_label, target.display_name)
    return {"status": "learning_started", "target_id": str(target_id)}


async def _run_learning_phase(target_id: uuid.UUID, prom_label: str, display_name: str):
    """Background task: analyze 30 days of historical data to build profiles."""
    logger.info(f"Learning phase started for {display_name}")
    prom = PrometheusClient()

    now = time.time()
    window_days = settings.LEARNING_WINDOW_DAYS

    try:
        timestamps, values = await prom.get_cpu_timeseries(
            prom_label,
            lookback_minutes=window_days * 24 * 60,
            step=60,  # 1-minute resolution for learning
        )
    except Exception as e:
        logger.error(f"Learning phase Prometheus query failed for {display_name}: {e}")
        return

    if len(values) < 100:
        logger.warning(f"Insufficient data for {display_name} learning phase ({len(values)} points).")
        return

    signal = detect_anomaly(timestamps, values, poll_interval_seconds=60)
    if not signal.is_anomaly:
        logger.info(f"No significant spikes found in learning window for {display_name}.")
        return

    spike = extract_spike_profile(timestamps, values, signal, poll_interval_seconds=60)
    if not spike:
        return

    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(MetricProfile)
            .where(MetricProfile.target_id == target_id)
            .where(MetricProfile.profile_name == "auto_learned")
        )
        existing_profile = existing.scalar_one_or_none()

        if existing_profile:
            existing_dict = {
                "mean_peak_cpu": existing_profile.mean_peak_cpu,
                "mean_rise_time_seconds": existing_profile.mean_rise_time_seconds,
                "mean_integral": existing_profile.mean_integral,
                "expected_duration_minutes": existing_profile.expected_duration_minutes,
                "std_duration_minutes": existing_profile.std_duration_minutes,
                "sample_count": existing_profile.sample_count,
            }
            updated = build_or_update_profile(existing_dict, spike)
            for k, v in updated.items():
                setattr(existing_profile, k, v)
        else:
            updated = build_or_update_profile(None, spike)
            new_profile = MetricProfile(
                target_id=target_id,
                profile_name="auto_learned",
                **updated,
            )
            db.add(new_profile)

        await db.commit()
        logger.info(f"Learning phase complete for {display_name}. Profile saved.")



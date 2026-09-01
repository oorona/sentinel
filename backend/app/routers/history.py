"""
History Router: Searchable incident history.
  GET /api/v1/history              — Paginated history with filters
  GET /api/v1/history/{id}         — Single incident detail
"""
import uuid
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_

from app.database import get_db
from app.models.incident import IncidentHistory
from app.models.target import Target
from app.schemas.incident import IncidentHistoryRead

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=list[IncidentHistoryRead])
async def list_history(
    target_id: Optional[uuid.UUID] = Query(None),
    classification: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    is_anomaly: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if target_id:
        filters.append(IncidentHistory.target_id == target_id)
    if classification:
        filters.append(IncidentHistory.classification == classification)
    if severity:
        filters.append(IncidentHistory.final_severity == severity)
    if is_anomaly is not None:
        filters.append(IncidentHistory.is_anomaly == is_anomaly)

    query = (
        select(IncidentHistory)
        .where(and_(*filters) if filters else True)
        .order_by(desc(IncidentHistory.start_ts))
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{incident_id}", response_model=IncidentHistoryRead)
async def get_incident(incident_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(IncidentHistory).where(IncidentHistory.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if not incident:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Incident not found.")
    return incident

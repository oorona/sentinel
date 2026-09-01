"""
Prompt Lab Router: CRUD for prompt templates + live testing.
  GET    /api/v1/prompts              — List templates
  POST   /api/v1/prompts              — Create template
  PUT    /api/v1/prompts/{id}         — Update template
  DELETE /api/v1/prompts/{id}         — Delete template
  POST   /api/v1/prompts/{id}/test    — Run a test with sample data
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.prompt_template import PromptTemplate
from app.schemas.prompt_template import PromptTemplateCreate, PromptTemplateUpdate, PromptTemplateRead
from app.services.gemini_service import gemini_service

router = APIRouter(prefix="/prompts", tags=["prompts"])

# Sample context for prompt testing
_SAMPLE_TEST_CONTEXT = {
    "target_info": {
        "name": "oracle-prod-01",
        "environment": "prod",
        "priority": 9,
        "db_type": "oracle",
    },
    "metrics": {
        "peak_cpu_percent": 94.5,
        "mad_zscore": 4.8,
        "rise_time_seconds": 12,
        "integral": 12500,
        "direction": "up",
        "recent_values": [15, 16, 18, 20, 85, 90, 94, 94, 92, 91],
    },
    "logs": (
        "2024-01-15 02:00:01 INFO  Oracle listener started\n"
        "2024-01-15 02:00:15 INFO  Batch job NIGHTLY_STATS started\n"
        "2024-01-15 02:00:30 ERROR ORA-04031: unable to allocate 65536 bytes of shared memory\n"
        "2024-01-15 02:01:00 ERROR ORA-00060: deadlock detected while waiting for resource\n"
        "2024-01-15 02:01:30 FATAL Connection refused: max connections exceeded\n"
    ),
    "history": {
        "profile_name": "nightly_batch",
        "expected_duration_minutes": 45.0,
        "actual_duration_minutes": 110.0,
        "overrun_minutes": 65.0,
        "mean_peak_cpu": 88.0,
        "sample_count": 14,
    },
    "trigger_reason": "Expected batch exceeded 120% of duration threshold",
}


@router.get("", response_model=list[PromptTemplateRead])
async def list_prompts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PromptTemplate).order_by(PromptTemplate.name))
    return result.scalars().all()


@router.post("", response_model=PromptTemplateRead, status_code=201)
async def create_prompt(body: PromptTemplateCreate, db: AsyncSession = Depends(get_db)):
    template = PromptTemplate(**body.model_dump())
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.put("/{template_id}", response_model=PromptTemplateRead)
async def update_prompt(
    template_id: uuid.UUID,
    body: PromptTemplateUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PromptTemplate).where(PromptTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(template, field, value)
    template.version += 1
    await db.commit()
    await db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=204)
async def delete_prompt(template_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PromptTemplate).where(PromptTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")
    await db.delete(template)
    await db.commit()


@router.post("/{template_id}/test")
async def test_prompt(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Run the template against a sample incident context and return full output."""
    result = await db.execute(select(PromptTemplate).where(PromptTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")

    output = await gemini_service.test_prompt(
        system_prompt=template.system_message,
        json_schema=template.json_schema,
        test_context=_SAMPLE_TEST_CONTEXT,
    )
    return {
        "template_name": template.name,
        "thought_process": output["thought_process"],
        "structured_output": output["structured_output"],
        "raw_json": output["raw_json"],
    }

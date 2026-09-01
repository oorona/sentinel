import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class PromptTemplateCreate(BaseModel):
    name: str
    system_message: str
    json_schema: dict


class PromptTemplateUpdate(BaseModel):
    system_message: Optional[str] = None
    json_schema: Optional[dict] = None
    is_active: Optional[bool] = None


class PromptTemplateRead(BaseModel):
    id: uuid.UUID
    name: str
    version: int
    system_message: str
    json_schema: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

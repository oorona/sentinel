import uuid
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class TargetCreate(BaseModel):
    label_name: str = Field(..., description="Prometheus 'instance' label value")
    display_name: str
    environment: Literal["dev", "test", "prod"]
    priority: int = Field(1, ge=1, le=10)
    auto_notify: bool = True
    prom_label: str = Field(..., description="Full Prometheus label selector e.g. 'instance=db-prod-01'")
    loki_label: Optional[str] = None
    db_type: Optional[Literal["oracle", "postgres", "mysql", "linux"]] = None


class TargetUpdate(BaseModel):
    display_name: Optional[str] = None
    environment: Optional[Literal["dev", "test", "prod"]] = None
    priority: Optional[int] = Field(None, ge=1, le=10)
    auto_notify: Optional[bool] = None
    prom_label: Optional[str] = None
    loki_label: Optional[str] = None
    db_type: Optional[str] = None


class TargetRead(BaseModel):
    id: uuid.UUID
    label_name: str
    display_name: str
    environment: str
    priority: int
    auto_notify: bool
    prom_label: str
    loki_label: Optional[str]
    db_type: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class MetricProfileRead(BaseModel):
    id: uuid.UUID
    target_id: uuid.UUID
    profile_name: str
    expected_duration_minutes: float
    std_duration_minutes: float
    mean_peak_cpu: float
    mean_rise_time_seconds: float
    mean_integral: float
    sample_count: int
    expected_hour_start: Optional[int]
    expected_hour_end: Optional[int]
    expected_dow: Optional[str]
    last_updated: datetime

    model_config = {"from_attributes": True}

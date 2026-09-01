import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class IncidentHistoryRead(BaseModel):
    id: uuid.UUID
    target_id: uuid.UUID
    start_ts: datetime
    end_ts: Optional[datetime]
    classification: str
    final_status: str
    is_anomaly: bool
    raw_metrics: Optional[dict]
    loki_logs_snapshot: Optional[str]
    llm_thought_process: Optional[str]
    llm_structured_output: Optional[dict]
    final_severity: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentAcknowledge(BaseModel):
    incident_id: str
    notes: Optional[str] = None


class ActiveIncident(BaseModel):
    id: str
    target_id: str
    target_name: str
    target_env: str
    target_priority: int
    classification: str  # detecting | expected | unexpected | overdue
    status: str          # active | ack | resolved
    start_ts: float      # Unix timestamp
    expected_end_ts: Optional[float] = None
    current_metric_value: Optional[float] = None
    profile_name: Optional[str] = None

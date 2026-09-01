import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Text, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class IncidentHistory(Base):
    __tablename__ = "incident_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("targets.id", ondelete="CASCADE"), index=True
    )
    start_ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    classification: Mapped[str] = mapped_column(String(50))  # expected | anomaly | overdue
    final_status: Mapped[str] = mapped_column(String(50), default="active")  # active | ack | resolved
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)

    # Metric snapshot
    raw_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    loki_logs_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    # LLM analysis
    llm_thought_process: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_structured_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    final_severity: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Profile reference
    matched_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("metric_profiles.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    target: Mapped["Target"] = relationship("Target", back_populates="incidents")

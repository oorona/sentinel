import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, Float, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    label_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    environment: Mapped[str] = mapped_column(String(50))  # dev | test | prod
    priority: Mapped[int] = mapped_column(Integer, default=1)
    auto_notify: Mapped[bool] = mapped_column(Boolean, default=True)
    prom_label: Mapped[str] = mapped_column(String(255))  # Prometheus instance label
    loki_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    db_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # oracle | postgres | mysql
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    profiles: Mapped[list["MetricProfile"]] = relationship(
        "MetricProfile", back_populates="target", cascade="all, delete-orphan"
    )
    incidents: Mapped[list["IncidentHistory"]] = relationship(
        "IncidentHistory", back_populates="target", cascade="all, delete-orphan"
    )


class MetricProfile(Base):
    """Statistical fingerprint of a known/expected event for a target."""
    __tablename__ = "metric_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("targets.id", ondelete="CASCADE"), index=True
    )
    profile_name: Mapped[str] = mapped_column(String(255))
    expected_duration_minutes: Mapped[float] = mapped_column(Float)
    std_duration_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    mean_peak_cpu: Mapped[float] = mapped_column(Float)
    mean_rise_time_seconds: Mapped[float] = mapped_column(Float)
    mean_integral: Mapped[float] = mapped_column(Float)
    sample_count: Mapped[int] = mapped_column(Integer, default=1)
    # Expected occurrence window (hour of day, day of week)
    expected_hour_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_hour_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_dow: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "1,2,3,4,5"
    last_updated: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    target: Mapped["Target"] = relationship("Target", back_populates="profiles")

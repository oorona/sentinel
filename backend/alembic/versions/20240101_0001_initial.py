"""initial

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "targets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("label_name", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("environment", sa.String(50), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("auto_notify", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("prom_label", sa.String(255), nullable=False),
        sa.Column("loki_label", sa.String(255), nullable=True),
        sa.Column("db_type", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("label_name", name="uq_targets_label_name"),
    )
    op.create_index("ix_targets_label_name", "targets", ["label_name"])

    op.create_table(
        "metric_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("target_id", UUID(as_uuid=True), nullable=False),
        sa.Column("profile_name", sa.String(255), nullable=False),
        sa.Column("expected_duration_minutes", sa.Float(), nullable=False),
        sa.Column("std_duration_minutes", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("mean_peak_cpu", sa.Float(), nullable=False),
        sa.Column("mean_rise_time_seconds", sa.Float(), nullable=False),
        sa.Column("mean_integral", sa.Float(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expected_hour_start", sa.Integer(), nullable=True),
        sa.Column("expected_hour_end", sa.Integer(), nullable=True),
        sa.Column("expected_dow", sa.String(20), nullable=True),
        sa.Column("last_updated", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["target_id"], ["targets.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_metric_profiles_target_id", "metric_profiles", ["target_id"])

    op.create_table(
        "incident_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("target_id", UUID(as_uuid=True), nullable=False),
        sa.Column("start_ts", sa.DateTime(), nullable=False),
        sa.Column("end_ts", sa.DateTime(), nullable=True),
        sa.Column("classification", sa.String(50), nullable=False),
        sa.Column("final_status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("is_anomaly", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("raw_metrics", JSONB(), nullable=True),
        sa.Column("loki_logs_snapshot", sa.Text(), nullable=True),
        sa.Column("llm_thought_process", sa.Text(), nullable=True),
        sa.Column("llm_structured_output", JSONB(), nullable=True),
        sa.Column("final_severity", sa.String(20), nullable=True),
        sa.Column("matched_profile_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["target_id"], ["targets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matched_profile_id"], ["metric_profiles.id"]),
    )
    op.create_index("ix_incident_history_target_id", "incident_history", ["target_id"])
    op.create_index("ix_incident_history_start_ts", "incident_history", ["start_ts"])

    op.create_table(
        "prompt_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("system_message", sa.Text(), nullable=False),
        sa.Column("json_schema", JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("name", name="uq_prompt_templates_name"),
    )


def downgrade() -> None:
    op.drop_table("prompt_templates")
    op.drop_index("ix_incident_history_start_ts", table_name="incident_history")
    op.drop_index("ix_incident_history_target_id", table_name="incident_history")
    op.drop_table("incident_history")
    op.drop_index("ix_metric_profiles_target_id", table_name="metric_profiles")
    op.drop_table("metric_profiles")
    op.drop_index("ix_targets_label_name", table_name="targets")
    op.drop_table("targets")

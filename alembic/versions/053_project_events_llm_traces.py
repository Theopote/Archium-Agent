"""Add project_events and llm_traces tables (Phase N engineering foundation)."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "053_project_events_llm_traces"
down_revision: str | None = "052_presentation_intent_slide_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "project_events" not in tables:
        op.create_table(
            "project_events",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("project_id", sa.Uuid(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("actor", sa.String(length=40), nullable=False, server_default="system"),
            sa.Column("event_type", sa.String(length=60), nullable=False, server_default="other"),
            sa.Column("summary", sa.String(length=800), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("dedupe_key", sa.String(length=200), nullable=False, server_default=""),
            sa.Column("source", sa.String(length=80), nullable=False, server_default=""),
        )
        op.create_index(
            "ix_project_events_project_id_at",
            "project_events",
            ["project_id", "at"],
        )
        op.create_index("ix_project_events_event_type", "project_events", ["event_type"])
        op.create_unique_constraint(
            "uq_project_events_dedupe",
            "project_events",
            ["project_id", "dedupe_key"],
        )

    if "llm_traces" not in tables:
        op.create_table(
            "llm_traces",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("request_id", sa.String(length=40), nullable=False),
            sa.Column(
                "project_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("projects.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("provider", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("model", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("capability", sa.String(length=80), nullable=True),
            sa.Column("model_role", sa.String(length=80), nullable=True),
            sa.Column("prompt_version", sa.String(length=80), nullable=True),
            sa.Column("prompt_tokens", sa.Integer(), nullable=True),
            sa.Column("completion_tokens", sa.Integer(), nullable=True),
            sa.Column("total_tokens", sa.Integer(), nullable=True),
            sa.Column("latency_ms", sa.Float(), nullable=True),
            sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("error_type", sa.String(length=120), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=False),
        )
        op.create_index(
            "ix_llm_traces_project_id_created",
            "llm_traces",
            ["project_id", "created_at"],
        )
        op.create_index("ix_llm_traces_request_id", "llm_traces", ["request_id"])
        op.create_index("ix_llm_traces_capability", "llm_traces", ["capability"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "llm_traces" in tables:
        op.drop_table("llm_traces")
    if "project_events" in tables:
        op.drop_table("project_events")

"""Add background_jobs and project_members tables (Phase N.2)."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "054_background_jobs_project_members"
down_revision: str | None = "053_project_events_llm_traces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "background_jobs" not in tables:
        op.create_table(
            "background_jobs",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "project_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("projects.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("kind", sa.String(length=40), nullable=False, server_default="generic"),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="queued"),
            sa.Column("label", sa.String(length=300), nullable=False, server_default=""),
            sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("message", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("result", sa.JSON(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index(
            "ix_background_jobs_status_created",
            "background_jobs",
            ["status", "created_at"],
        )
        op.create_index(
            "ix_background_jobs_project_id_created",
            "background_jobs",
            ["project_id", "created_at"],
        )
        op.create_index("ix_background_jobs_kind", "background_jobs", ["kind"])

    if "project_members" not in tables:
        op.create_table(
            "project_members",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "project_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("projects.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("actor_id", sa.String(length=200), nullable=False),
            sa.Column("display_name", sa.String(length=200), nullable=False, server_default=""),
            sa.Column("role", sa.String(length=40), nullable=False, server_default="architect"),
        )
        op.create_unique_constraint(
            "uq_project_members_project_actor",
            "project_members",
            ["project_id", "actor_id"],
        )
        op.create_index("ix_project_members_project_id", "project_members", ["project_id"])
        op.create_index("ix_project_members_actor_id", "project_members", ["actor_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "project_members" in tables:
        op.drop_table("project_members")
    if "background_jobs" in tables:
        op.drop_table("background_jobs")
